#!/usr/bin/env python3 -m stk.cli

from __future__ import annotations

import functools
import typing
import click
import boto3
import json
import yaml

from dataclasses import dataclass
from os import environ
from rich.table import Table
from rich.prompt import Confirm
from rich.padding import Padding

from . import VERSION, console
from .config import Config
from .stack import Stack
from .template import TemplateWithConfig
from .change_set import ChangeSet

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@dataclass
class StackDelegatedCommand:
    name: str
    environment: str
    config_path: str
    template_path: str
    var: typing.List
    param: typing.List

    def __post_init__(self):
        vars = parse_overrides(self.var)
        params = parse_overrides(self.param)
        self.config = Config(
            name=self.name,
            environment=self.environment,
            config_path=self.config_path,
            template_path=self.template_path,
            var_overrides=vars,
            param_overrides=params,
        )
        self.stack = Stack(aws=self.config.aws, name=self.config.core.stack_name)
        self.stack_name = self.stack.name

    def __getattr__(self, name):
        if hasattr(self.stack, name):
            return getattr(self.stack, name)
        return super().__getattr__(name)

    def show_outputs(self):
        outputs = self.outputs()
        if outputs:
            t = Table("Key", "Value", "Description", title="Stack Outputs", title_justify="left", title_style="bold")
            for key, value in outputs.items():
                t.add_row(key, value, value.description)
            console.print(t)
        else:
            console.print(f"Stack {self.stack_name} does not have any outputs")


class TemplateCommand(StackDelegatedCommand):
    def __post_init__(self):
        super().__post_init__()
        self.template = TemplateWithConfig(provider=self.config.template_source.provider(), config=self.config).render()

        parse_error = self.template.error
        if parse_error:
            console.log(f":x: Template is NOT ok - {parse_error}", emoji=True, style="red")
            console.print(str(self.template))
            exit(-1)

    def validate(self):
        template = self.template
        if not template.error:
            errors = self.stack.validate(template)
            if errors:
                console.log(f"{errors}\n\n", style="red")
                console.log(":x: Template is NOT ok - failed validation", emoji=True, style="red")
                console.print(str(self.template))
                exit(-1)
            else:
                console.log(":+1: Template is ok", emoji=True, style="green")

    def create_change_set(self, change_set_name=None) -> ChangeSet:
        with console.status("Creating change set"):
            tags = self.config.tags.to_list()
            params = self.config.params
            cs = self.stack.create_change_set(template=self.template, tags=tags, change_set_name=change_set_name, params=params)
        return cs


def common_stack_params(func):
    """Decorator for commands that need same stack/environment parameters"""

    @click.argument("name")
    @click.argument("environment")
    @click.option("--config-path", default=environ.get("CONFIG_PATH", "."), help="Path to config project")
    @click.option("--template-path", default=environ.get("TEMPLATE_PATH", "."), help="Path to templates")
    @click.option("--var", help="override configuration variable", multiple=True)
    @click.option("--param", help="override CFN parameter", multiple=True)
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=VERSION)
def stk():
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
    """
    Create a new stack
    """
    sc = TemplateCommand(**kwargs)
    if sc.exists():
        console.log(f"Stack {sc.stack_name} already exists", style="red")
        exit(-1)

    console.log("Creating stack", sc.stack_name, style="blue")

    with console.status("Validating template") as status:
        sc.validate()

    change_set = sc.create_change_set()
    console.log("Change set created")

    console.print(change_set.summary())

    if not change_set.available():
        console.log(":x: Change set could not be generated", emoji=True, style="red")
        exit(-2)

    if yes or Confirm.ask(f"Create stack {sc.stack_name} ?"):
        console.rule()
        console.log(f"Applying change set")
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
        console.log(f"Stack {sc.name} does not exist")
        exit(-1)

    sc.validate()

    console.log("Diff:\n", sc.diff(sc.template))

    change_set = sc.create_change_set()

    console.log("Change set:\n", change_set.summary())

    if not change_set.available():
        console.log(":x: Change set could not be generated", emoji=True, style="red")
        exit(-2)

    if yes or Confirm.ask(f"Update stack {sc.stack_name} ?"):
        console.rule()
        console.log(f"Applying change set")

        change_set.execute()
        if sc.wait("stack_update_complete", change_set.resources()):
            console.log("Stack updated successfully", style="green")
            if sc.outputs():
                sc.show_outputs()
        else:
            console.log("Stack update failed", style="red")
            exit(-2)

@stk.command()
@common_stack_params
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
@click.pass_context
def upsert(context, yes: bool, **kwargs):
    """
    Create or update stack
    """
    sc = TemplateCommand(**kwargs)

    if sc.exists():
        context.forward(update)
    else:
        context.forward(create)

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
        StackDelegatedCommand(**kwargs).execute_change_set(change_set_name=change_set_name)
        console.log(":+1: Change set complete", emoji=True, style="green")
        if sc.outputs():
            sc.show_outputs()
    except sc.cfn.exceptions.ChangeSetNotFoundException as ex:
        console.log(":x: Change set does not exist", emoji=True, style="red")


@stk.command()
@common_stack_params
@click.argument("change_set_name")
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
def delete_change_set(change_set_name: str, yes: bool, **kwargs):
    """
    Deletes named change set.
    """
    sc = StackDelegatedCommand(**kwargs)
    console.log(f"Deleting change set {change_set_name} for {sc.stack_name}")
    try:
        sc.delete_change_set(change_set_name=change_set_name)
        console.log("Change set deleted")
    except sc.cfn.exceptions.ChangeSetNotFoundException as ex:
        console.log(":x: Change set does not exist", style="red", emoji=True)


@stk.command()
@common_stack_params
@click.option("--yes", is_flag=True, show_default=True, default=False, help="Automatically approve changeset")
def delete(yes: bool, **kwargs):
    sc = StackDelegatedCommand(**kwargs)
    if not sc.exists():
        console.log(f"Stack {sc.stack_name} does not exist", style="red")
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
@click.option("--format", default="yaml", help="Force conversion of resulting template (json or yaml)")
@click.option("--output-file", default="", help="Write resulting template to file")
def show_template(name: str, environment: str, config_path: str, template_path: str, format: str, output_file: str, var: typing.List, param: typing.List):
    config = Config(
        name=name,
        environment=environment,
        config_path=config_path,
        template_path=template_path,
        var_overrides=parse_overrides(var),
        param_overrides=parse_overrides(param),
    )
    template = TemplateWithConfig(provider=config.template_source.provider(), config=config)

    result = template.render()
    if result.error:
        console.log(f":x: Template is NOT ok - {result.error}", emoji=True, style="red")
        console.print(str(result))
        exit(-1)

    result = str(result)

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
        console.print(result)


@stk.command()
@common_stack_params
def diff(**kwargs):
    sc = TemplateCommand(**kwargs)
    if not sc.exists():
        console.log(f"Stack {sc.name} does not exist", style="red")
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
    sc = StackDelegatedCommand(**kwargs)

    console.log(f"Retrieving outputs for {sc.name}")

    if not sc.exists():
        console.log(f"Stack {sc.name} does not exist", style="red")
        return

    sc.show_outputs()


@stk.command()
@common_stack_params
def show_config(name: str, environment: str, config_path: str, template_path: str, var: typing.List, param: typing.List):
    config = Config(name=name, environment=environment, config_path=config_path, var_overrides=parse_overrides(var), param_overrides=parse_overrides(param))

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

    console.print(template_table, "\n")
    console.print(params_table, "\n")
    console.print(vars_table, "\n")


def parse_overrides(overrides: typing.List):
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


if __name__ == "__main__":
    stk()
