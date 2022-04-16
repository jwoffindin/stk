from __future__ import annotations

import boto3

from botocore.exceptions import ClientError, WaiterError
from datetime import datetime
from rich.table import Table
from rich.console import Console

from .stack_waiter import StackWaiter
from .config import Config
from .template import RenderedTemplate


class StackException(Exception):
    def __init__(self, stack: Stack, message: str, response=None):
        super().__init__(message)
        self.stack = stack
        self.response = response


class Stack:
    def __init__(self, aws: Config.AwsSettings, name: str):
        self.aws = aws
        self.name = name

        self.cfn = boto3.client("cloudformation", region_name=self.aws.region)
        self.s3 = boto3.client("s3", region_name=self.aws.region)

        self.bucket_name = aws.cfn_bucket

    def validate(self, template: RenderedTemplate):
        template_url = self.upload(template)
        self.cfn.validate_template(TemplateURL=template_url)

    def create(self, template: RenderedTemplate):
        if self.exists():
            print(f"Stack {self.name} already exists")
            return None

        return self.create_and_apply_change_set("create", template)

    def update(self, template: RenderedTemplate):
        if not self.exists():
            print(f"Stack {self.name} does not exist")
            return None

        return self.create_and_apply_change_set("update", template)

    def create_and_apply_change_set(self, action: str, template: RenderedTemplate):
        change_set_name = datetime.now().strftime(f"stack-{action}-%Y%m%d%H%M%S")
        change_set = self.create_change_set(template, change_set_name)

        self.print_change_set(change_set)
        if change_set["ExecutionStatus"] != "AVAILABLE":
            # TODO Delete change set
            return

        self.execute_change_set(change_set["ChangeSetId"])

    def print_change_set(self, c):
        t = Table("Property", "Value", title="Change Set")
        t.add_row("Stack Name", c.get("StackName", "-"))
        t.add_row("Stack ID", c.get("StackId", "-"))
        t.add_row("Execution Status", c.get("ExecutionStatus", "-"))
        t.add_row("Status", c.get("Status", "-"))
        t.add_row("Reason", c.get("StatusReason", "-"))

        c = Console().print(t)

        print(c)

    def create_change_set(self, template: RenderedTemplate, change_set_name: str):
        print(f"Creating change set {change_set_name} for {self.name}")

        change_set_type = "CREATE" if not self.exists() else "UPDATE"

        template_url = self.upload(template)
        res = self.cfn.create_change_set(
            StackName=self.name,
            TemplateURL=template_url,
            ChangeSetName=change_set_name,
            ChangeSetType=change_set_type,
        )

        try:
            self.wait("change_set_create_complete", ChangeSetName=res["Id"])
        except WaiterError as ex:
            pass
        return self.cfn.describe_change_set(ChangeSetName=res["Id"])

    def delete_change_set(self, change_set_name: str):
        print(f"Deleting change set {change_set_name}")
        res = self.cfn.delete_change_set(StackName=self.name, ChangeSetName=change_set_name)
        return res["ResponseMetadata"]["HTTPStatusCode"] == 200

    def execute_change_set(self, change_set_name):
        print(f"Applying change set {change_set_name} to {self.name}")
        self.cfn.execute_change_set(StackName=self.name, ChangeSetName=change_set_name)
        self.wait("stack_create_complete", StackName=self.name)

    def delete(self):
        if not self.exists():
            print(f"Stack {self.name} does not exist")
            return

        print(f"Destroying stack {self.name}")
        self.cfn.delete_stack(StackName=self.name)
        self.wait("stack_delete_complete", StackName=self.name)

    def upload(self, template):
        template_path = "/".join([template.md5(), template.name])
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=template_path,
            Body=bytes(template.content, "utf-8"),
            ServerSideEncryption="AES256",
        )
        return self.bucket_url(template_path)

    def bucket_url(self, *path) -> str:
        bucket_hostname = f"{self.bucket_name}.s3.{self.aws.region}.amazonaws.com"
        return "/".join(["https:/", bucket_hostname, *path])

    def exists(self):
        return self.status() != None

    def status(self):
        try:
            stack = self.cfn.describe_stacks(StackName=self.name)["Stacks"][0]
            assert self.name in [stack["StackId"], stack["StackName"]]
            return stack["StackStatus"]
        except ClientError as e:
            err = e.response["Error"]
            if (err["Code"] == "ValidationError") and ("does not exist" in err["Message"]):
                return None
            raise (e)

    def wait(self, waiter_name, **kwargs):
        resources = {}
        StackWaiter(self).wait(waiter_name, resources, **kwargs)
