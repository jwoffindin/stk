from __future__ import annotations
from pathlib import Path
from typing import Union

import yaml


from . import log


class ConfigFiles(list):
    def fetch_dict(self, key, environment, defaults: dict = {}):
        ret_val = dict(defaults)

        for config_file in self:
            # Top-level key in file is lowest priority
            try:
                ret_val.update(config_file.get(key, {}))
            except TypeError as ex:
                self.report_error(f"Unable to retrieve top-level key '{key}'", config_file, key, ex)

            # Environment-specific key is higher priority
            try:
                ret_val.update(config_file.environment(environment).get(key, {}))
            except TypeError as ex:
                self.report_error(f"Unable to retrieve {key} from environments.{environment}", config_file, key, ex)

        return ret_val

    def fetch_set(self, key, environment, defaults: list = []):
        ret_val = set(defaults)

        for config_file in self:
            ret_val.update(config_file.get(key, []))
            ret_val.update(config_file.environment(environment).get(key, []))

        return ret_val

    def validate(self, config):
        valid_environments = config.core.environments
        if valid_environments:
            for include in self:
                include.validate(valid_environments)

    def report_error(self, msg: str, config_file: ConfigFile, key: str, err: Exception):
        print(msg + f" while processing {config_file.filename}: {err}")
        exit(-1)

class ConfigObject(dict):
    """Base object representing a source of configuration - multiple ConfigObjects are merged to generate final configuration by ConfigFiles"""
    EXPECTED_KEYS = set(["aws", "core", "environments", "helpers", "includes", "params", "refs", "tags", "template", "vars"])

    # almost all keys can appear under 'environments:'... except environments
    EXPECTED_ENV_KEYS = EXPECTED_KEYS - set(['environments'])

    def __init__(self):
        super().__init__()
        self.filename = "anonymous"
        self["vars"] = {}
        self["params"] = {}
        self["includes"] = []
        self["helpers"] = []
        self["environments"] = {}
        self["refs"] = {}
        self["template"] = {}
        self["tags"] = {}


    def _ensure_valid_keys(self):
        """
        Ensure config file only contains expected keys
        """
        unknown_keys = set(self.keys()) - self.EXPECTED_KEYS

        if unknown_keys:
            raise Exception(f"Config file {self.filename} has unexpected keys: {unknown_keys}")

        for env_name, env_settings in self["environments"].items():
            if env_settings:  # handle case with blank environment
                unknown_env_keys = set(env_settings.keys()) - self.EXPECTED_ENV_KEYS
                if unknown_env_keys:
                    raise Exception(f"Config file {self.filename} environments.{env_name} has unexpected keys: {unknown_env_keys}")

    def environments(self) -> list:
        """
        Return list of environments defined in this config file. Normally the top-level config is
        special in that it defines which environments a stack can be deployed into - even if the
        included configs defined additional environments.
        """
        return list(self["environments"].keys())

    def environment(self, environment) -> dict:
        """
        Returns environment section from a config file. Returns empty dict if not defined, or None.
        """
        return self["environments"].get(environment, None) or {}

    def validate(self, valid_environments):
        if "environments" in self:
            defined_envs = set(self["environments"].keys())
            invalid_envs = defined_envs - set(valid_environments)
            if invalid_envs:
                invalid_envs = ", ".join(invalid_envs)
                valid_envs = ", ".join(valid_environments)
                raise Exception(f"{self.filename} defines environments {invalid_envs}, which are not listed in core.environments ({valid_envs})")

    def _post_init(self, cfg: Union[dict, None]):
        # hack 'template: [ name: 'template_name' } shortcut
        if cfg and "template" in cfg and isinstance(cfg["template"], str):
            cfg["template"] = {"name": cfg["template"]}

        if cfg:
            log.debug("ConfigObject: initializing from %s", cfg)
            self.update(cfg)

        # check that an environment matching one of the reserved keys isn't defined - highly
        # likely that user has fat-fingered their config
        reserved_env_errors = self.EXPECTED_KEYS & set(self["environments"].keys())
        if reserved_env_errors:
            raise Exception(f"{self.filename} has defined environments {reserved_env_errors}; these are reserved")

        self._ensure_valid_keys()



class ConfigDocument(ConfigObject):
    """A static document representing configuration - used to allow user to provide overrides"""
    def __init__(self, config: Union[dict, None]):
        super().__init__()
        self._post_init(config)

class ConfigFile(ConfigObject):
    """A ConfigObject loaded from file (in the config dir)"""
    def __init__(self, filename: str, config_dir: str):
        super().__init__()
        self.config_dir = config_dir
        self.filename = str(self._find_config_file(Path(filename)))

        filepath = Path(config_dir, self.filename)
        try:
            cfg = yaml.safe_load(open(filepath, "r", encoding="utf-8")) or dict()
        except yaml.parser.ParserError as ex:
            log.fatal("Unable to load configuration file %s", filepath, exc_info=ex)
            raise

        self._post_init(cfg)

    def includes(self):
        """
        Returns list of included files (relative to config dir). Files will be given .yml extension
        if they don't have an extension already
        """
        includes = self["includes"]
        if not isinstance(includes, list):
            raise Exception(f"{self.filename} invalid `includes` directive. Expect a list, got a {type(includes)}")

        # Build a list of ['include/file-1.yml', 'include/file-2.yml]...
        include_paths = []
        for included in includes:
            p = self._find_config_file(Path("includes", included))
            include_paths.append(str(p))
        return include_paths


    def load_includes(self, overrides: Union[ConfigFiles, None] = None) -> ConfigFiles:
        """
        Returns list of config objects with highest precedence last (lowest first)
        """
        config_objects = ConfigFiles([include for include in self._load_includes(seen = set()) if include])
        if overrides:
            config_objects.extend(overrides)
        return config_objects

    def _load_includes(self, seen) -> list:
        """
        Recursive loading of includes. Returns a list with lowest-precedence first.

        E.g. if A includes B, and B includes C then a._load_includes() returns [C, B, A]
        """
        includes = []
        for include in self.includes():
            if include not in seen:
                seen.add(include)
                included = ConfigFile(include, self.config_dir)._load_includes(seen)
                includes += included

        includes += [self]

        return includes

    def _find_config_file(self, p: Path):
        if p.suffix:
            return p

        for suffix in [".yaml", ".yml"]:
            p = p.with_suffix(suffix)
            if Path(self.config_dir, p).exists():
                return p

        raise FileNotFoundError(f"{p.with_suffix('')} does not exist (tried .yaml,.yml)")
