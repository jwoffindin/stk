import typing
import json


def parse_overrides(overrides: typing.List):
    """
    Parse user-provided cli argument into dict; used to allow user to pass
    var and param overrides on the command-line.
    """
    ret_val = {}
    for v in overrides:
        key, value = v.split("=", 1)
        try:
            # try parsing value as a JSON object. E.g. user can do --var 'foo=[123]'
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            # value passed may not have been json, e.g. user may have just done
            # --var foo=bar ; shortcut for having to do --var 'foo="bar"'
            parsed_value = value
        ret_val[key] = parsed_value

    return ret_val
