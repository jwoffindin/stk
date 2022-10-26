VERSION = "0.7.0"

import os
import logging

from rich.console import Console

logging.basicConfig(filename="stk.log", filemode="w", level=os.environ.get("LOG_LEVEL", "INFO").upper())

console = Console(emoji=False, log_path=False)
clog = console.log


class ConfigException(Exception):
    pass
