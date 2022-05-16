VERSION = "0.0.1"

import os
import logging

from rich.console import Console

logging.basicConfig(filename="stk.log", filemode="w", level=os.environ.get("LOG_LEVEL", "INFO").upper())


console = Console()
clog = console.log


class ConfigException(Exception):
    pass
