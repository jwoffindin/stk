from __future__ import annotations

import boto3

from botocore.exceptions import ClientError
from datetime import datetime, timezone

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
        change_set_name = datetime.now().strftime("stack-create-%Y%m%d%H%M%S")
        change_set = self.create_change_set(template, change_set_name)

        if change_set["ExecutionStatus"] != "AVAILABLE":
            raise Exception(f"Changeset could not be created (status={change_set['ExecutionStatus']}")

        self.execute_change_set(change_set["ChangeSetId"])

    def create_change_set(self, template: RenderedTemplate, change_set_name: str):
        print(f"Creating change set {change_set_name} for {self.name}")

        template_url = self.upload(template)
        res = self.cfn.create_change_set(
            StackName=self.name,
            TemplateURL=template_url,
            ChangeSetName=change_set_name,
            ChangeSetType="CREATE",
        )

        if "Id" not in res:
            raise StackException(self, "Could not create change set", response=res)

        self.wait("change_set_create_complete", ChangeSetName=res["Id"])
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
        StackWaiter(self).wait(waiter_name, **kwargs)
