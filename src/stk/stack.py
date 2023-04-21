from __future__ import annotations

from typing import List
from random import choice
from string import ascii_letters
from botocore.exceptions import ClientError, WaiterError
from difflib import unified_diff

from . import log
from .stack_waiter import StackWaiter
from .template import RenderedTemplate
from .basic_stack import BasicStack
from .change_set import ChangeSet


class StackException(Exception):
    def __init__(self, stack: Stack, message: str, response=None):
        super().__init__(message)
        self.stack = stack
        self.response = response


class Stack(BasicStack):
    DIFF_CONTEXT_LINES = 5

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def validate(self, template: RenderedTemplate):
        """Validate template"""
        log.warning("Validating template")
        try:
            self.cfn.validate_template(TemplateURL=self.bucket.upload(template).as_http())
        except ClientError as ex:
            log.warning(ex.response)
            if ex.response["Error"]["Code"] == "ValidationError":
                return ex
            raise

    def create_change_set(self, template: RenderedTemplate, tags: List(str) = [], change_set_name: str = None, params: dict = {}) -> ChangeSet:
        """
        Creates a ChangeSet object for given template.

        :param change_set_name: Change set name. Short random string will be generated if none provided

        """
        if not change_set_name:
            change_set_name = "".join((choice(ascii_letters) for _ in range(12)))

        status = self.status()
        change_set_type = "UPDATE" if status and status != "REVIEW_IN_PROGRESS" else "CREATE"

        return ChangeSet(self, change_set_name).create(template=template, change_set_type=change_set_type, tags=tags, params=params)

    def execute_change_set(self, change_set_name: str) -> bool:
        """
        Execute named change set.

        Returns truthy value if successful
        """

        waiter_name = "stack_update_complete" if self.status() != "REVIEW_IN_PROGRESS" else "stack_create_complete"

        change_set = ChangeSet(self, change_set_name)
        change_set.execute()

        try:
            StackWaiter(self).wait_for_stack(waiter_name, change_set.resources())
            return True
        except WaiterError as ex:
            print("Change set could not be applied:", ex)

    def delete_change_set(self, change_set_name: str):
        ChangeSet(self, change_set_name).delete()

    def delete(self):
        # Get list of resources before we start deleting them
        resources = self.resources()
        self.cfn.delete_stack(StackName=self.name)
        StackWaiter(self).wait_for_stack("stack_delete_complete", resources=resources)

    def diff(self, template: RenderedTemplate) -> str:
        """
        Return text-based diff between currently deployed stack template and the proposed
        (local) template.
        """
        # Compare currently deployed stack template...
        current_template = self.cfn.get_template(StackName=self.name, TemplateStage="Original")
        from_lines = current_template["TemplateBody"].splitlines()

        # against the one just compiled
        to_lines = template.content.splitlines()

        changes = list(unified_diff(from_lines, to_lines, fromfile="Deployed", tofile="Local", n=self.DIFF_CONTEXT_LINES, lineterm=""))

        if not len(changes):
            return "[yellow]There are no changes (template is identical)[/yellow]"

        diff = []
        for change in changes:
            if change.startswith("@@"):
                diff.append(f"[bold]{change}[/bold]")
            elif change.startswith("-"):
                diff.append(f"[red]{change}[/red]")
            elif change.startswith("+"):
                diff.append(f"[green]{change}[/green]")
            else:
                diff.append(change)

        return "\n".join(diff)

    def resources(self) -> dict:
        ret_val = {}

        paginator = self.cfn.get_paginator("list_stack_resources")
        for resources in paginator.paginate(StackName=self.name):
            for resource in resources["StackResourceSummaries"]:
                ret_val[resource["LogicalResourceId"]] = resource["ResourceType"]

        return ret_val

    def wait(self, waiter_name, resources):
        try:
            StackWaiter(self).wait_for_stack(waiter_name, resources)
            return True
        except WaiterError as ex:
            print("Change could not be applied:", ex)
