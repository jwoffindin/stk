import boto3

from .config import Config
from .template import RenderedTemplate
class Stack:
    def __init__(self, aws: Config.AwsSettings):
        self.aws = aws

        self.cfn = boto3.client("cloudformation", region_name=self.aws.region)
        self.s3  = boto3.client("s3", region_name=self.aws.region)

        self.bucket_name = "foo"

    def validate(self, template: RenderedTemplate):
        template_url = self.upload(template)

        self.cfn.validate_template(TemplateURL=template_url)

        return None


    def upload(self, template):
        template_path = "/".join([template.md5(), template.name])
        self.s3.put_object(Bucket=self.bucket_name, Key=template_path, Body=bytes(template.content, 'utf-8'), ServerSideEncryption="AES256")
        return self.bucket_url(template_path)


    def bucket_url(self, *path) -> str:
        bucket_hostname = f'{self.bucket_name}.s3.{self.aws.region}.amazonaws.com'
        return "/".join(['https:/', bucket_hostname, *path])

