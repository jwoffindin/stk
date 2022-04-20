from __future__ import annotations
from dataclasses import dataclass
from typing import List

import boto3

from botocore.exceptions import ClientError, WaiterError
from datetime import datetime
from rich.table import Table
from rich.console import Console
from rich.prompt import Confirm

from .stack_waiter import StackWaiter
from .template import RenderedTemplate
from .cfn_bucket import CfnBucket
from .aws_config import AwsSettings
from .basic_stack import BasicStack


class StackException(Exception):
    def __init__(self, stack: Stack, message: str, response=None):
        super().__init__(message)
        self.stack = stack
        self.response = response


class Stack(BasicStack):
    def __init__(self, aws: AwsSettings, name: str):
        super().__init__(aws, name)
        self.bucket = CfnBucket(aws)

    def validate(self, template: RenderedTemplate):
        self.cfn.validate_template(TemplateURL=self.bucket.upload(template).as_s3())

    def create(self, template: RenderedTemplate):
        if self.exists():
            print(f"Stack {self.name} already exists")
            return None

        if not self.create_and_apply_change_set("create", template):
            self.delete()

    def update(self, template: RenderedTemplate):
        if not self.exists():
            print(f"Stack {self.name} does not exist")
            return None

        return self.create_and_apply_change_set("update", template)

    def create_and_apply_change_set(self, action: str, template: RenderedTemplate):
        """
        Creates a change set for given template (stack may, or may not, exist already)

        Returns a false value if change could not be applied (or user cancels apply).
        """
        change_set_name = datetime.now().strftime(f"stack-{action}-%Y%m%d%H%M%S")
        change_set = self.create_change_set(template, change_set_name)

        if change_set["ExecutionStatus"] == "AVAILABLE" and Confirm.ask(f"{action.capitalize()} {self.name} ?"):
            return self.execute_change_set(action=action, change_set_name=change_set["ChangeSetId"])

        return None

    def create_change_set(self, template: RenderedTemplate, change_set_name: str):
        print(f"Creating change set {change_set_name} for {self.name}")

        status = self.status()
        change_set_type = "UPDATE" if status and status != "REVIEW_IN_PROGRESS" else "CREATE"

        template_url = self.bucket.upload(template).as_http()
        res = self.cfn.create_change_set(
            StackName=self.name,
            TemplateURL=template_url,
            ChangeSetName=change_set_name,
            ChangeSetType=change_set_type,
            Capabilities=template.iam_capabilities(),
        )

        try:
            self.wait_for_change_set("change_set_create_complete", res["Id"])
        except WaiterError as ex:
            pass

        change_set = self.cfn.describe_change_set(ChangeSetName=res["Id"])
        self.print_change_set(change_set)

        return change_set

    def delete_change_set(self, change_set_name: str):
        print(f"Deleting change set {change_set_name}")
        res = self.cfn.delete_change_set(StackName=self.name, ChangeSetName=change_set_name)
        return res["ResponseMetadata"]["HTTPStatusCode"] == 200

    def execute_change_set(self, action: str, change_set_name: str):
        print(f"Applying change set {change_set_name} to {self.name}")

        change_set = self.cfn.describe_change_set(ChangeSetName=change_set_name)
        self.cfn.execute_change_set(StackName=self.name, ChangeSetName=change_set_name)

        try:
            self.wait_for_stack(f"stack_{action}_complete", change_set)
            return True
        except WaiterError as ex:
            print("Change set could not be applied:", ex)

    def delete(self):
        if not self.exists():
            print(f"Stack {self.name} does not exist")
            return

        print(f"Destroying stack {self.name}")
        res = self.cfn.delete_stack(StackName=self.name)
        self.wait_for_stack("stack_delete_complete")
        print("Stack deleted")

    def wait_for_stack(self, waiter_name, change_set=None):
        StackWaiter(self).wait_for_stack(waiter_name, change_set)

    def wait_for_change_set(self, waiter_name, change_set_name):
        StackWaiter(self).wait_for_change_set(waiter_name, change_set_name)

    def print_change_set(self, change_set):
        if change_set["ExecutionStatus"] == "AVAILABLE":
            detail = Table("Resource", "Type", "Action", "Scope", "Details")
            for rc in self.resources_change_in_changeset(change_set):
                detail.add_row(
                    rc["LogicalResourceId"], rc["ResourceType"], rc["Action"], str(rc.get("Scope", "-")), self.humanize_change_detail(rc.get("Details"))
                )
            change_set = Console().print(detail)
        else:
            summary = Table("Property", "Value", title="Change Set")
            summary.add_row("Stack Name", change_set.get("StackName", "-"))
            summary.add_row("Stack ID", change_set.get("StackId", "-"))
            summary.add_row("Execution Status", change_set.get("ExecutionStatus", "-"))
            summary.add_row("Status", change_set.get("Status", "-"))
            summary.add_row("Reason", change_set.get("StatusReason", "-"))

            Console().print(summary)

    def humanize_change_detail(self, change_details: List[dict]) -> str:
        ret_val = []
        for change in change_details or []:
            try:
                target = change["Target"]
                target_name = "[b]%s.%s[/b]" % (target["Attribute"], target["Name"])
                if change["ChangeSource"] == "DirectModification":
                    ret_val.append(f"{target_name} changed")
                elif change["ChangeSource"] == "ResourceAttribute":
                    ret_val.append(f"{target_name} changed by {change['CausingEntity']}")
                else:
                    ret_val.append(str(change))
            except Exception as ex:
                print(ex)
                ret_val.append(str(change))
        return "\n".join(ret_val)

    def resources_change_in_changeset(self, cs):
        if "Changes" in cs:
            for change in cs["Changes"]:
                if "ResourceChange" in change:
                    rs = change["ResourceChange"]
                    yield (rs)
