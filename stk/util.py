import yaml
from typing import List, Dict, Union

from . import log
from .config_file import ConfigDocument, ConfigFiles

def parse_overrides(cfg_vars: List[str], cfg_params: List[str], overrides: str) -> ConfigFiles:
    """
    Build a ConfigFiles list that provides ConfigFiles list from
    vars/params and generic 'overrides' dict.
    """
    log.debug("parsing overrides params; vars=%s, params=%s, overrides=%s", cfg_vars, cfg_params, overrides)
    configs = ConfigFiles([
        ConfigDocument(parse_override_yaml(overrides)),
        ConfigDocument({"vars": parse_override_list(cfg_vars)}),
        ConfigDocument({"params": parse_override_list(cfg_params)}),
    ])

    log.debug("created overrides: %s", configs)

    return configs

def parse_override_list(overrides: List):
    """
    Parse user-provided cli argument into dict; used to allow user to pass
    var and param overrides on the command-line.
    """
    ret_val = {}
    for kv in overrides:
        key, value = kv.split("=", 1)
        try:
            # try parsing value as a YAML object. E.g. user can do --var 'foo=[123]'
            parsed_value = yaml.safe_load(value)
        except yaml.YAMLError:
            # value passed may not have been yaml, e.g. user may have just done
            # --var foo=bar ; shortcut for having to do --var 'foo="bar"'
            parsed_value = value
        ret_val[key] = parsed_value

    return ret_val

def parse_override_yaml(overrides: Union[str, None]) -> Dict:
    """
    Parse yaml object passed on the command-line

    Can be a yaml-esque string, or @filename, to load
    """
    if overrides:
        if overrides.startswith('@'):
            filename = overrides[1:]
            with open(filename, 'r', encoding="utf-8") as fh:
                return yaml.safe_load(fh)

        return yaml.safe_load(overrides)
