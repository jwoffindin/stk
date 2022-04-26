from __future__ import annotations

import re

from dataclasses import dataclass
from jinja2 import Environment, StrictUndefined
from pathlib import Path
from sys import exc_info
from yaml import safe_load

from . import ConfigException
from .config_file import ConfigFile
from .template_source import TemplateSource
from .basic_stack import BasicStack
from .aws_config import AwsSettings


class Config:
    @dataclass
    class InterpolationError:
        key: str
        value: str
        error: str

    @dataclass
    class CoreSettings:
        # Attributes
        stack_name: str

        # DEFAULTS are pre-interpolation values so can't set them via attributes
        DEFAULTS = {"stack_name": "{{ environment }}-{{ name }}"}

        # stack name
        valid_stack_name = re.compile("^(i?)[a-z0-9-]+$").match

        def __post_init__(self):
            if type(self.stack_name) != str or not self.valid_stack_name(self.stack_name):
                raise ValueError(f"Stack name {self.stack_name} is invalid. Can contain only alphanumeric characters and hyphens")

    class Vars(dict):
        MAX_INTERPOLATION_DEPTH = 10

        def __init__(self, vars: dict):
            """
            We want to expand interpolated 'vars' using Jinja2.

            This is a bit different than how to expand other Jinja-value dicts because we'll need to iterate through a few
            times until all vars have been expanded.
            """
            failed_keys = self.expand(vars)

            if failed_keys:
                raise Exception(f"An error occurred: {failed_keys}")

        def expand(self, vars: dict):
            """
            Updates `self` with final interpolated values from initial dict `vars`.

            Returns dict InterpolationError for all keys that can't be expanded
            """
            env = Environment(undefined=StrictUndefined)

            interpolation_depth = 0

            errors = {}
            while interpolation_depth <= self.MAX_INTERPOLATION_DEPTH:
                interpolation_depth += 1
                unexpanded_keys = sorted(set(vars.keys()) - set(self.keys()))
                if not unexpanded_keys:
                    return None

                for key in unexpanded_keys:
                    value = vars[key]
                    try:
                        del errors[key]
                        if type(value) in [bool, dict, list, str]:
                            tpl = env.from_string(str(value))  # convert value to jinja2 template
                            result = str(tpl.render(self))
                            self[key] = safe_load(result) or ""
                        else:
                            self[key] = value  # Don't try and process this value as Jinja template
                        del vars[key]
                    except Exception:
                        errors[key] = Config.InterpolationError(key, value, exc_info()[1])

            return errors

    class InterpolatedDict(dict):
        def __init__(self, object: dict, vars: dict):
            # Handle loading from empty YAML file (results in None), or a 'config group' (e.g. params)
            # not being present - which is okay.
            if not object:
                return

            if type(object) != dict:
                raise Exception(object)

            env = Environment(undefined=StrictUndefined)

            for k, v in object.items():
                try:
                    value = env.from_string(str(v)).render(vars)
                    parsed_value = safe_load(value)
                    if parsed_value != None:
                        self[k] = parsed_value
                except Exception as ex:
                    raise (Exception(f"Unable to process {k}, value={object[k]} : {ex}"))

    class StackRefs:
        DEFAULTS = {"stack_name": "{{ environment }}-{{ name }}", "optional": False}

        def __init__(self, stack_refs: dict, config: Config):
            self.config = config
            self.refs = stack_refs

        def __contains__(self, name: str) -> bool:
            return name in self.stacks()

        def __getitem__(self, name: str) -> str:
            return self.stack(name)

        def output(self, name: str, output_name: str) -> str:
            return self.stack(name).output(output_name)

        def stack(self, name: str) -> BasicStack:
            stacks = self.stacks()
            if name not in self.stacks():
                raise Exception(f"Attempt to access stack {name}, but it's not defined in config refs (only {', '.join(stacks.keys())} defined)")

            return stacks[name]

        def stacks(self) -> dict:
            if not hasattr(self, "_stacks"):
                self._stacks = dict()
                for name, cfg in self.refs.items():
                    if name == "environment":
                        continue

                    final_opts = Config.InterpolatedDict({**self.DEFAULTS, **cfg}, {**self.config.vars, "name": name.replace("_", "-")})
                    stk = BasicStack(aws=self.config.aws, name=final_opts["stack_name"])
                    if stk.exists() or final_opts["optional"]:
                        self._stacks[name] = stk
                    else:
                        raise Exception(f"Stack reference {name} - {stk.name} does not exist, but is required")
            return self._stacks

    def __init__(
        self,
        name: str,
        environment: str,
        config_path: str,
        template_path: str = None,
        var_overrides: dict = {},
        param_overrides: dict = {},
    ):
        self.name = name
        self.environment = environment
        self.config_path = config_path

        try:
            filename = Path(name)
            if not filename.suffix:
                filename = filename.with_suffix(".yaml")

            cfg = ConfigFile(filename=filename, config_dir=self.config_path)
        except FileNotFoundError as err:
            print("Configuration file {cfg.filename} not found in {config.path}")
            raise

        # Validate specified environment is defined in the top-level config file
        if environment not in cfg.environments():
            raise ConfigException(f"Environment {environment} is not a valid environment for {cfg.filename}. Only {cfg.environments()} permitted.")

        includes = cfg.load_includes()

        #
        self.aws = AwsSettings(**includes.fetch_dict("aws", environment))

        # Stack 'refs' object references external stacks. They are intended to be resolved by 'vars'/'params' so need to be
        # loaded first
        self.refs = self.StackRefs(includes.fetch_dict("refs", environment), self)

        self.vars = self.Vars(includes.fetch_dict("vars", environment, {"name": name, "environment": environment, "refs": self.refs}))
        self.params = self.InterpolatedDict(includes.fetch_dict("params", environment), self.vars)

        self.helpers = list(includes.fetch_set("helpers", environment))
        self.core = self.CoreSettings(
            **self.InterpolatedDict(
                includes.fetch_dict("core", environment, self.CoreSettings.DEFAULTS),
                self.vars,
            )
        )
        self.template_source = TemplateSource(
            **self.InterpolatedDict(
                includes.fetch_dict(
                    "template",
                    environment,
                    {"name": name, "version": "main", "repo": template_path},
                ),
                self.vars,
            )
        )

    def var(self, name):
        return self.vars.get(name)

    def param(self, name):
        return self.params.get(name)
