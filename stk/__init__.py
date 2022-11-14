VERSION = "0.8.0"

import os
import logging
import yaml

from rich.console import Console

logging.basicConfig(filename="stk.log", filemode="w", level=os.environ.get("LOG_LEVEL", "INFO").upper())

console = Console(emoji=False, log_path=False)
clog = console.log

yaml.SafeDumper.add_representer(type(None), lambda x, value: x.represent_scalar("tag:yaml.org,2002:null", ""))


class ConfigException(Exception):
    pass
