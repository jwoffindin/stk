#!/usr/bin/env python3 -m stk.cli

from __future__ import annotations

import functools
import json

from typing import List
from os import environ

import click
import boto3
import yaml
from click_aliases import ClickAliasedGroup
from rich.table import Table
from rich.prompt import Confirm
from rich.padding import Padding

from . import VERSION, console
from .config import Config
from .config_cmd import cli
from .stack_delegated_command import StackDelegatedCommand
from .template import TemplateWithConfig
from .template_command import TemplateCommand
from .util import parse_overrides

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def common_stack_params(func):
    """Decorator for commands that need same stack/environment parameters"""

    @click.argument("name")
    @click.argument("environment")
    @click.option("--config-path", default=environ.get("CONFIG_PATH", "."), help="Path to config project")
    @click.option("--template-path", default=environ.get("TEMPLATE_PATH", "."), help="Path to templates")
    @click.option("--var", help="override configuration variable", multiple=True)
    @click.option("--param", help="override CFN parameter", multiple=True)
    @click.option("--overrides", help="override generic config")
    @click.option("--outputs-format", type=click.Choice(['table', 'json', 'yaml'], case_sensitive=False), default="table", help="Force conversion of resulting template (json, yaml or table)")
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@click.group(context_settings=CONTEXT_SETTINGS, cls=ClickAliasedGroup)
@click.version_option(version=VERSION)
def stk():
    """
    Primary command object for CLI
    """
    log_level = environ.get("LOG_LEVEL", None)
    if log_level:
        boto3.set_stream_logger("boto3", level=log_level)
        boto3.set_stream_logger("botocore", level=log_level)
        boto3.set_stream_logger("boto3.resources", level=log_level)


# Register config subcommands
stk.add_command(cli.config)


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
    """
    Create a new stack
    """
    sc = TemplateCommand(**kwargs)
    if sc.exists():
        console.log(f"Stack {sc.stack_name} already exists", style="red")
        exit(-1)

    console.log("Creating stack", sc.stack_name, style="blue")

    with console.status("Validating template"):
        sc.validate()

    change_set = sc.create_change_set()
    console.log("Change set created")

    console.print(change_set.summary())

    if not change_set.available():
        console.log(":x: Change set could not be generated",
                    emoji=True, style="red")
        exit(-2)

    if yes or Confirm.ask(f"Create stack {sc.stack_name} ?"):
        console.rule()
        console.log("Applying change set")
        change_set.execute()
        if sc.wait("stack_create_complete", change_set.resources()):
            console.log("Stack created successfully", style="green")
            if sc.outputs():
                sc.show_outputs()
        else:
            console.log("Stack create failed", style="red")
            exit(-2)
    else:
        console.log("Cleaning up")
        sc.delete()


@stk.command()
@common_stack_params
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
def update(yes: bool, **kwargs):
    """
    Update an existing stack via changeset
    """
    sc = TemplateCommand(**kwargs)

    if not sc.exists():
        console.log(f"Stack {sc.name} does not exist in {sc.config.aws.region}")
        exit(-1)

    sc.validate()

    console.log("Diff:\n", sc.diff(sc.template))

    change_set = sc.create_change_set()

    console.log("Change set:\n", change_set.summary())

    if not change_set.available():
        if change_set.is_empty_changeset():
            console.log(":poop: No changes to be applied",
                        emoji=True, style="blue")
            exit(-9)
        else:
            console.log(":x: Change set could not be generated",
                        emoji=True, style="red")
            exit(-2)

    if yes or Confirm.ask(f"Update stack {sc.stack_name} ?"):
        console.rule()
        console.log("Applying change set")

        change_set.execute()
        if sc.wait("stack_update_complete", change_set.resources()):
            console.log("Stack updated successfully", style="green")
            if sc.outputs():
                sc.show_outputs()
        else:
            console.log("Stack update failed", style="red")
            exit(-2)


@stk.command(aliases=['deploy'])
@common_stack_params
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
@click.pass_context
def upsert(context, yes: bool, **kwargs):
    """
    Create or update stack
    """
    stack = TemplateCommand(**kwargs)

    if stack.exists():
        context.forward(update, yes=yes)
    else:
        context.forward(create, yes=yes)


@stk.command()
@common_stack_params
@click.argument("change_set_name")
def create_change_set(change_set_name: str, **kwargs):
    """
    Create named changeset
    """
    sc = TemplateCommand(**kwargs)

    console.log(f"Creating change set {change_set_name} for {sc.stack_name}")

    # Fail fast
    sc.validate()

    if sc.exists():
        # Only diff if the stack exists
        console.log("Diff:\n", sc.diff(sc.template))

    change_set = sc.create_change_set(change_set_name=change_set_name)

    console.print(Padding(change_set.summary(), (0, 10)))

    if change_set.available():
        console.log(":+1: Change set created", emoji=True)
    else:
        console.log(":x: Change set was not successful", emoji=True)


@stk.command()
@common_stack_params
@click.argument("change_set_name")
def execute_change_set(change_set_name: str, **kwargs):
    sc = StackDelegatedCommand(**kwargs)

    console.log(f"Executing change set {change_set_name} for {sc.stack_name}")
    try:
        StackDelegatedCommand(
            **kwargs).execute_change_set(change_set_name=change_set_name)
        console.log(":+1: Change set complete", emoji=True, style="green")
        if sc.outputs():
            sc.show_outputs()
    except sc.cfn.exceptions.ChangeSetNotFoundException:
        console.log(":x: Change set does not exist", emoji=True, style="red")


@stk.command()
@common_stack_params
@click.argument("change_set_name")
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
def delete_change_set(change_set_name: str, yes: bool, **kwargs): # pylint: disable=unused-argument
    """
    Deletes named change set.
    """
    sc = StackDelegatedCommand(**kwargs)
    console.log(f"Deleting change set {change_set_name} for {sc.stack_name}")
    try:
        sc.delete_change_set(change_set_name=change_set_name)
        console.log("Change set deleted")
    except sc.cfn.exceptions.ChangeSetNotFoundException:
        console.log(":x: Change set does not exist", style="red", emoji=True)


@stk.command()
@common_stack_params
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
def delete(yes: bool, **kwargs):
    sc = StackDelegatedCommand(**kwargs)
    if not sc.exists():
        console.log(f"Stack {sc.stack_name} does not exist in {sc.config.aws.region}", style="red")
        exit(-1)

    if not (yes or Confirm.ask(f"Delete stack {sc.stack_name} ?")):
        console.log("Aborting")
        exit(-2)

    console.rule()
    console.log(f"Destroying stack {sc.stack_name}")
    sc.delete()
    console.log("Stack deleted")


@stk.command()
@common_stack_params
@click.option("--format", "format_", default="yaml", help="Force conversion of resulting template (json or yaml)")
@click.option("--output-file", default="", help="Write resulting template to file")
def show_template(name: str, environment: str, config_path: str, template_path: str, format_: str, output_file: str, outputs_format: str, var: List, param: List, overrides: str):
    config_overrides = parse_overrides(var, param, overrides)
    config = Config(
        name=name,
        environment=environment,
        config_path=config_path,
        template_path=template_path,
        overrides=config_overrides,
    )
    template = TemplateWithConfig(
        provider=config.template_source.provider(), config=config)

    result = template.render()
    if result.error:
        console.log(
            f":x: Template is NOT ok - {result.error}", emoji=True, style="red")
        console.print(str(result))
        exit(-1)

    result = str(result)

    if format_ == "yaml":
        pass
    elif format_ == "json":
        result = json.dumps(yaml.safe_load(result), indent=4, sort_keys=True)
    else:
        raise Exception("Unknown output format")

    if output_file:
        with open(output_file, "w", encoding="utf-8") as file:
            file.write(result)
    else:
        console.print(result)


@stk.command()
@common_stack_params
def diff(**kwargs):
    sc = TemplateCommand(**kwargs)
    if not sc.exists():
        console.log(f"Stack {sc.name} does not exist in {sc.config.aws.region}", style="red")
        return

    d = sc.diff(sc.template)
    if d:
        console.log("Generated diff")
        console.print(d)
        # console.log(d)
    else:
        console.log("There are no changes (templates are identical)")


@stk.command()
@common_stack_params
def outputs(**kwargs):
    """Command to display stack outputs"""
    sc = StackDelegatedCommand(**kwargs)

    console.log(f"Retrieving outputs for {sc.name}")

    if not sc.exists():
        console.log(f"Stack {sc.name} does not exist in {sc.config.aws.region}", style="red")
        return

    sc.show_outputs()


@stk.command()
@common_stack_params
def show_config(name: str, environment: str, config_path: str, template_path: str, outputs_format: str, var: List, param: List, overrides: str):
    config = Config(name=name, environment=environment, config_path=config_path, overrides=parse_overrides(var, param, overrides))

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

    cfg_vars = config.vars
    vars_table = Table("Variable", "Value", "Type", title="Variables")
    for k in sorted(cfg_vars.keys()):
        v = cfg_vars[k]
        vars_table.add_row(k, str(v), type(v).__name__)

    tags = config.tags
    tags_table = Table("Tag", "Value")
    for k in sorted(tags.keys()):
        v = tags[k]
        tags_table.add_row(k, str(v))

    console.print(template_table, "\n")
    console.print(params_table, "\n")
    console.print(vars_table, "\n")
    console.print(tags_table, "\n")


if __name__ == "__main__":
    stk()
