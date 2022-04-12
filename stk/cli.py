#!/usr/bin/env python3 -m stk.cli

import click

from os import environ
from rich.console import Console
from rich.table import Table

from . import VERSION
from .config import Config
from .template import Template


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=VERSION)
def stk():
    pass


@stk.command()
@click.argument('stack')
@click.argument('env')
@click.option('--config-path', default=environ.get('CONFIG_PATH', '.'), help='Path to config project')
@click.option('--template-path', default=environ.get('TEMPLATE_PATH', '.'), help='Path to templates')
def show_template(stack: str, env: str, config_path: str, template_path: str):
    config = Config(name=stack, environment=env, config_path=config_path, template_path=template_path)

    template = Template(provider=config.template.provider())
    rendered = template.render(config.vars)

    print(rendered)


@stk.command()
@click.argument('stack')
@click.argument('env')
@click.option('--config-path', default=environ.get('CONFIG_PATH', '.'), help='Path to config project')
def show_config(stack: str, env: str, config_path: str):
    config = Config(name=stack, environment=env, config_path=config_path)

    template = config.template
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
