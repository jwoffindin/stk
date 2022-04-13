import boto3

from datetime import datetime

from .config import Config
from .template import RenderedTemplate
class StackException(Exception):
    def __init__(self, stack, message, response = None):
        super().__init__(message)

        self.stack = stack
        self.response = response
class Stack:
    def __init__(self, aws: Config.AwsSettings, name: str):
        self.aws = aws
        self.name = name

        self.cfn = boto3.client("cloudformation", region_name=self.aws.region)
        self.s3  = boto3.client("s3", region_name=self.aws.region)

        self.bucket_name = "foo"

    def validate(self, template: RenderedTemplate):
        template_url = self.upload(template)

        self.cfn.validate_template(TemplateURL=template_url)

        return None

    def create(self, template: RenderedTemplate):
        change_set_name = datetime.now().strftime('stack-create-%Y%m%d%H%M%S')
        change_set = self.create_change_set(template, change_set_name)

        if change_set['ExecutionStatus'] != 'AVAILABLE':
            raise Exception(f"Changeset could not be created (status={change_set['ExecutionStatus']}")

        self.execute_change_set(change_set)


    def create_change_set(self, template: RenderedTemplate, change_set_name: str):
        template_url = self.upload(template)

        res = self.cfn.create_change_set(StackName=self.name, TemplateURL=template_url, ChangeSetName=change_set_name, ChangeSetType='CREATE')

        if 'Id' not in res:
            raise StackException(self, "Could not create change set", response=res)

        return self.cfn.describe_change_set(StackName=self.name, ChangeSetName=res['Id'])

    def execute_change_set(self, change_set):
        return self.cfn.execute_change_set(StackName=self.name, ChangeSetName=change_set['ChangeSetId'])

    def upload(self, template):
        template_path = "/".join([template.md5(), template.name])
        self.s3.put_object(Bucket=self.bucket_name, Key=template_path, Body=bytes(template.content, 'utf-8'), ServerSideEncryption="AES256")
        return self.bucket_url(template_path)

    def bucket_url(self, *path) -> str:
        bucket_hostname = f'{self.bucket_name}.s3.{self.aws.region}.amazonaws.com'
        return "/".join(['https:/', bucket_hostname, *path])

