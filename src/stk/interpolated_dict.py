from dataclasses import dataclass
from typing import Any, Dict
from jinja2 import Environment, StrictUndefined
from yaml import safe_load

class InterpolatedDict(dict):
    def __init__(self, object: Dict[str, Any], vars: Dict[str, Any]):
        # Handle loading from empty YAML file (results in None), or a 'config group' (e.g. params)
        # not being present - which is okay.
        if not object:
            return

        if type(object) != dict:
            raise Exception(object)

        env = Environment(undefined=StrictUndefined, extensions=["jinja2_strcase.StrcaseExtension"])

        for key, value in object.items():
            try:
                if value == None:
                    self[key] = None
                else:
                    value = env.from_string(str(value)).render(vars)
                    parsed_value = safe_load(value)
                    if parsed_value != None:
                        self[key] = parsed_value
            except Exception as ex:
                raise Exception(f"Unable to process {key}, value={object[key]}") from ex



@dataclass
class InterpolationError:
    """Captures information about an error occurring during evaluation of variables"""

    key: str
    value: str
    error: str
