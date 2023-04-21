"""
"""
import logging
import logging.handlers
import yaml

from os import environ
from rich.console import Console

VERSION = "0.15.0"

# Create application logger (for when things go wrong)
log = logging.getLogger('cfn')
log.setLevel(environ.get('CFN_LOG_LEVEL', environ.get("LOG_LEVEL", "WARN")).upper())

if environ.get('LOG_FILE'):
    logging.basicConfig(filename=environ['LOG_FILE'], filemode="a")
else:
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    formatter = logging.Formatter('cfn: %(message)s')
    log.addHandler(handler)


# Console logger is for displaying updates to user - normal
# events.
console = Console(emoji=False, log_path=False, stderr=True)
clog = console.log

# This makes yaml.dump() output `foo: ` rather than `foo: null`
#
yaml.SafeDumper.add_representer(
    type(None),
    lambda x, value: x.represent_scalar("tag:yaml.org,2002:null", "")
)


class ConfigException(Exception):
    """
    Needs a new home - supposed to be base class for any configuration
    based errors.
    """
    pass
