from __future__ import annotations
from os import path
from pathlib import Path
from yaml import safe_load

class ConfigFiles(list):
    def fetch_dict(self, key, environment, defaults: dict = {}):
        ret_val = dict(defaults)

        for config_file in self:
            # Top-level key in file is lowest priority
            ret_val.update(config_file.get(key, {}))

            # Environment-specific key is higher priority
            ret_val.update(config_file.environment(environment).get(key, {}))

        return ret_val

    def fetch_set(self, key, environment, defaults: list = []):
        ret_val = set(defaults)

        for config_file in self:
            ret_val.update(config_file.get(key, []))
            ret_val.update(config_file.environment(environment).get(key, []))

        return ret_val


class ConfigFile(dict):
    EXPECTED_KEYS = ['vars', 'params', 'environments', 'include', 'helpers', 'template']

    def __init__(self, filename: str, config_dir: str):
        self.filename = filename
        self.config_dir = config_dir

        self['vars'] = {}
        self['params'] = {}
        self['include'] = []
        self['helpers'] = []
        self['environments'] = {}

        config_path = path.join(config_dir, filename)

        cfg = safe_load(open(config_path)) or dict()
        super().__init__(cfg)
        self._ensure_valid_keys()

    def _ensure_valid_keys(self):
        """
        Ensure config file only contains expected keys
        """
        unknown_keys = set(self.keys()) - set(self.EXPECTED_KEYS)

        if unknown_keys:
            raise Exception(f"Config file {self.filename} has unexpected keys: {unknown_keys}")

    def environments(self) -> list:
        """
        Return list of environments defined in this config file. Normally the top-level config is
        special in that it defines which environments a stack can be deployed into - even if the
        included configs defined additional environments.
        """
        return list(self['environments'].keys())

    def environment(self, environment) -> dict:
        """
        Returns environment section from a config file. Returns empty dict if not defined, or None.
        """
        return self['environments'].get(environment, None) or {}

    def includes(self):
        """
        Returns list of included files (relative to config dir). Files will be given .yml extension
        if they don't have an extension already
        """
        includes = self['include']
        if type(includes) != list:
            raise Exception(f'{self.filename} invalid `include` directive. Expect a list, got a {type(includes)}')

        # Build a list of ['include/file-1.yml', 'include/file-2.yml]...
        include_paths = []
        for included in includes:
            p = Path('includes', included)
            if not p.suffix:
                p = p.with_suffix('.yaml')
            include_paths.append(str(p))
        return include_paths

    def load_includes(self) -> list:
        """
        Returns list of config files with highest precedence last (lowest first)
        """
        includes = self._load_includes(set())
        return ConfigFiles(include for include in includes if include)

    def _load_includes(self, seen) -> list:
        """
        Recursive loading of includes. Returns a list with lowest-precedence first.j

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
