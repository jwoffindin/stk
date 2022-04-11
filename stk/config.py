
from os import path
from sys import exc_info
from yaml import safe_load
from jinja2 import Template, Environment, StrictUndefined
from dataclasses import dataclass

class ConfigFile(dict):
    EXPECTED_KEYS = ['vars', 'params', 'environments']
    def __init__(self, filename: str):
        self.filename = filename

        self['vars'] = {}
        self['params'] = {}

        cfg = safe_load(open(filename)) or dict()
        super().__init__(cfg)
        self._ensure_valid_keys()

    def _ensure_valid_keys(self):
        """
        Ensure config file only contains expected keys
        """
        unknown_keys = set(self.keys()) - set(self.EXPECTED_KEYS)

        if unknown_keys:
            raise Exception(f"Config file {self.filename} has unexpected keys: {unknown_keys}")

class Config:
    @dataclass
    class InterpolationError:
        key: str
        value: str
        error: str
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

            print(f"final {self}")

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
                print(f'unexpanded = {unexpanded_keys}')

                if not unexpanded_keys:
                    return None

                for key in unexpanded_keys:
                    print("Processing " + key)
                    value = vars[key]
                    print(value)
                    try:
                        if type(value) in [bool, dict, list, str]:
                            tpl = env.from_string(str(value)) # convert value to jinja2 template
                            result = str(tpl.render(self))

                            value = safe_load(result) or ""
                            self[key] = value
                        else:
                            # Don't try and process this value as Jinja template
                            self[key] = value
                        del errors[key]
                        del vars[key]
                    except Exception:
                        errors[key] = Config.InterpolationError(key, value, exc_info()[1])

            return errors

    class InterpolatedDict(dict):
        def __init__(self, object, vars):
            # Handle loading from empty YAML file (results in None), or a 'config group' (e.g. params)
            # not being present - which is okay.
            if not object:
                return

            env = Environment(undefined=StrictUndefined)

            for k, v in object.items():
                try:
                    value = env.from_string(str(v)).render(vars)
                    parsed_value = safe_load(value)
                    if parsed_value != None:
                        self[k] = parsed_value
                except Exception as ex:
                    raise(Exception(f"Unable to process {k}, value={object[k]} : {ex}"))


    def __init__(self, name: str, environment: str, config_path: str, var_overrides: dict = {}, param_overrides: dict = {}):
        self.name = name
        self.environment = environment
        self.config_path = config_path

        self._cfg = ConfigFile(path.join(config_path, name + '.yml'))
        self._vars = Config.Vars(self._cfg['vars'])
        self._params = Config.InterpolatedDict(self._cfg['params'], self._vars)


    def vars(self):
        return self._vars

    def var(self, name):
        return self._vars.get(name)

    def params(self):
        return self._params

    def param(self, name):
        if name not in self._params:
            return None
        return self._params[name]
