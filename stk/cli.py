#!/usr/bin/env python3 -m stk.cli

import functools
import click

from os import environ
from rich.console import Console
from rich.table import Table

from . import VERSION
from .config import Config
# from .stack import Stack
from .template import TemplateWithConfig

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

# Add @common_stack_params decorator for commands that need stack/environment
def common_stack_params(func):
    @click.argument('stack')
    @click.argument('env')
    @click.option('--config-path', default=environ.get('CONFIG_PATH', '.'), help='Path to config project')
    @click.option('--template-path', default=environ.get('TEMPLATE_PATH', '.'), help='Path to templates')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=VERSION)
def stk():
    pass

@stk.command()
@common_stack_params
def validate(stack: str, env: str, config_path: str, template_path: str):
    config = Config(name=stack, environment=env, config_path=config_path, template_path=template_path)
    template = TemplateWithConfig(config.template_source.provider(), config)

    aws_settings = config.aws
    print(aws_settings)
    # stack = Stack(aws=config.aws)
    # stack.validate(template=template.render(fail_on_error=True))


@stk.command()
@common_stack_params
def show_template(stack: str, env: str, config_path: str, template_path: str):
    config = Config(name=stack, environment=env, config_path=config_path, template_path=template_path)
    template = TemplateWithConfig(config.template_source.provider(), config)
    print(template.render())


@stk.command()
@common_stack_params
def show_config(stack: str, env: str, config_path: str, template_path: str):
    config = Config(name=stack, environment=env, config_path=config_path)

    template = config.template_source
    template_table = Table("Property", "Value", title="Template Source")
    template_table.add_row("Template Name", template.name)
    template_table.add_row("Version", template.version)
    template_table.add_row("Source", template.repo)

    params = config.params
    params_table = Table("Parameter", "Value", "Type", title="Parameters")
    for k in sorted(params.keys()):
        v = params[k]
        params_table.add_row(k, str(v), type(v).__name__)

    vars = config.vars
    vars_table = Table("Variable", "Value", "Type", title="Variables")
    for k in sorted(vars.keys()):
        v = vars[k]
        vars_table.add_row(k, str(v), type(v).__name__)


    console = Console()
    console.print(template_table, "\n")
    console.print(params_table, "\n")
    console.print(vars_table, "\n")

if __name__ == '__main__':
    stk()
