#!/usr/bin/env python3 -m stk.cli

from __future__ import annotations

import functools
import click
import botocore
import boto3
import json
import yaml

from dataclasses import dataclass
from os import environ
from pytest import fail
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
from rich.padding import Padding
from rich.panel import Panel

from . import VERSION
from .config import Config
from .stack import Stack
from .template import TemplateWithConfig, Template

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@dataclass
class StackDelegatedCommand:
    name: str
    environment: str
    config_path: str
    template_path: str

    def __post_init__(self):
        self.config = Config(name=self.name, environment=self.environment, config_path=self.config_path, template_path=self.template_path)
        self.stack = Stack(aws=self.config.aws, name=self.config.core.stack_name)
        self.stack_name = self.stack.name

    def __getattr__(self, name):
        if hasattr(self.stack, name):
            return getattr(self.stack, name)
        return super().__getattr__(name)


class TemplateCommand(StackDelegatedCommand):
    def __post_init__(self):
        super().__post_init__()
        self.template = TemplateWithConfig(provider=self.config.template_source.provider(), config=self.config).render()

        parse_error = self.template.error
        if parse_error:
            c.log(f":x: Template is NOT ok - {parse_error}", style="red")
            exit(-1)

    def validate(self):
        template = self.template
        if not template.error:
            errors = self.stack.validate(template)
            if errors:
                c.log(f"{errors}\n\n", style="red")
                c.log(":x: Template is NOT ok - failed validation", style="red")
                exit(-1)
            else:
                c.log(":+1: Template is ok", style="green")

    def create_change_set(self, change_set_name=None) -> ChangeSet:
        with c.status("Creating change set"):
            tags = self.config.tags.to_list()
            cs = self.stack.create_change_set(template=self.template, tags=tags, change_set_name=change_set_name)
        return cs


def common_stack_params(func):
    """Decorator for commands that need same stack/environment parameters"""

    @click.argument("name")
    @click.argument("environment")
    @click.option("--config-path", default=environ.get("CONFIG_PATH", "."), help="Path to config project")
    @click.option("--template-path", default=environ.get("TEMPLATE_PATH", "."), help="Path to templates")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=VERSION)
def stk():
    global c
    c = Console()

    log_level = environ.get("LOG_LEVEL", None)
    if log_level:
        boto3.set_stream_logger("boto3", level=log_level)
        boto3.set_stream_logger("botocore", level=log_level)
        boto3.set_stream_logger("boto3.resources", level=log_level)


@stk.command()
@common_stack_params
def validate(**kwargs):
    """Validate provided template"""
    sc = TemplateCommand(**kwargs)
    sc.validate()


@stk.command()
@common_stack_params
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
def create(yes: bool, **kwargs):
    sc = TemplateCommand(**kwargs)
    if sc.exists():
        c.log(f"Stack {sc.stack_name} already exists", style="red")
        exit(-1)

    c.log("Creating stack", sc.stack_name, style="blue")

    with c.status("Validating template") as status:
        sc.validate()

    change_set = sc.create_change_set()
    c.log("Change set created")

    c.print(change_set.summary())

    if not change_set.available():
        c.log(":x: Change set could not be generated", style="red")
        exit(-2)

    if yes or Confirm.ask(f"Create stack {sc.stack_name} ?"):
        change_set.execute()
        if sc.wait("stack_create_complete", change_set.resources()):
            c.log("Stack created successfully", style="green")
        else:
            c.log("Stack create failed", style="red")
            exit(-2)
    else:
        c.log("Cleaning up")
        sc.delete()


@stk.command()
@common_stack_params
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
def update(yes: bool, **kwargs):
    sc = TemplateCommand(**kwargs)

    if not sc.exists():
        c.log(f"Stack {sc.name} does not exist")
        exit(-1)

    sc.validate()

    c.log("Diff:\n", sc.diff(sc.template))

    change_set = sc.create_change_set()

    c.log("Change set:\n", change_set.summary())

    if not change_set.available():
        c.log(":x: Change set could not be generated", style="red")
        exit(-2)

    if yes or Confirm.ask(f"Update stack {sc.stack_name} ?"):
        change_set.execute()
        if sc.wait("stack_update_complete", change_set.resources()):
            c.log("Stack updated successfully", style="green")
        else:
            c.log("Stack update failed", style="red")
            exit(-2)


@stk.command()
@common_stack_params
@click.argument("change_set_name")
def create_change_set(change_set_name: str, **kwargs):
    sc = TemplateCommand(**kwargs)

    c.log(f"Creating change set {change_set_name} for {sc.stack_name}")

    # Fail fast
    sc.validate()

    if sc.exists():
        # Only diff if the stack exists
        c.log("Diff:\n", sc.diff(sc.template))

    change_set = sc.create_change_set(change_set_name=change_set_name)

    c.print(Padding(change_set.summary(), (0, 10)))

    if change_set.available():
        c.log(":+1: Change set created")
    else:
        c.log(":x: Change set was not successful")


@stk.command()
@common_stack_params
@click.argument("change_set_name")
def execute_change_set(change_set_name: str, **kwargs):
    sc = StackDelegatedCommand(**kwargs)

    c.log(f"Executing change set {change_set_name} for {sc.stack_name}")
    try:
        StackDelegatedCommand(**kwargs).execute_change_set(change_set_name=change_set_name)
        c.log(":+1: Change set complete")
    except sc.cfn.exceptions.ChangeSetNotFoundException as ex:
        c.log(":x: Change set does not exist", style="red")


@stk.command()
@common_stack_params
@click.argument("change_set_name")
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
def delete_change_set(change_set_name: str, yes: bool, **kwargs):
    """
    Deletes named change set.
    """
    sc = StackDelegatedCommand(**kwargs)
    c.log(f"Deleting change set {change_set_name} for {sc.stack_name}")
    try:
        sc.delete_change_set(change_set_name=change_set_name)
        c.log("Change set deleted")
    except sc.cfn.exceptions.ChangeSetNotFoundException as ex:
        c.log(":x: Change set does not exist", style="red")


@stk.command()
@common_stack_params
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
def delete(yes: bool, **kwargs):
    sc = StackDelegatedCommand(**kwargs)
    if not sc.exists():
        c.log(f"Stack {sc.stack_name} does not exist", style="red")
        exit(-1)

    if not (yes or Confirm.ask(f"Delete stack {sc.stack_name} ?")):
        c.log("Aborting")
        exit(-2)
    c.log(f"Destroying stack {sc.stack_name}")
    sc.delete()
    c.log("Stack deleted")


@stk.command()
@common_stack_params
@click.option("--format", default="yaml", help="Force conversion of resulting template (json or yaml)")
@click.option("--output-file", default="", help="Write resulting template to file")
def show_template(name: str, environment: str, config_path: str, template_path: str, format: str, output_file: str):
    config = Config(name=name, environment=environment, config_path=config_path, template_path=template_path)
    template = TemplateWithConfig(provider=config.template_source.provider(), config=config)

    result = str(template.render())

    if format == "yaml":
        pass
    elif format == "json":
        result = json.dumps(yaml.safe_load(result), indent=4, sort_keys=True)
    else:
        raise Exception("Unknown output format")

    if output_file:
        fh = open(output_file, "w")
        fh.write(result)
        fh.close()
    else:
        c.print(result)


@stk.command()
@common_stack_params
def diff(**kwargs):
    sc = TemplateCommand(**kwargs)
    if not sc.exists():
        c.log(f"Stack {self.name} does not exist", style="red")
        return

    d = sc.diff(sc.template)
    if d:
        c.log("Generated diff")
        c.print(d)
        # c.log(d)
    else:
        c.log("There are no changes (templates are identical)")


@stk.command()
@common_stack_params
def show_config(name: str, environment: str, config_path: str, template_path: str):
    config = Config(name=name, environment=environment, config_path=config_path)

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


if __name__ == "__main__":
    stk()
