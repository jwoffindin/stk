from __future__ import annotations

import boto3

from dataclasses import dataclass

from .config import Config


class Uploadable:
    def body(self) -> bytes:
        pass

    def key(self) -> str:
        pass


@dataclass
class CfnBucketObject:
    bucket: CfnBucket
    key: str

    def as_http(self) -> str:
        s3_hostname = f"{self.bucket.bucket_name}.s3.{self.bucket.region}.amazonaws.com"
        return "/".join(["https:/", s3_hostname, self.key])

    def s3(self) -> str:
        return "/".join(["s3:/", self.bucket.bucket_name, self.key])


class CfnBucket:
    def __init__(self, config: Config.AwsSettings):
        self.region = config.region
        self.bucket_name = config.cfn_bucket

        self.s3 = boto3.client("s3", region_name=self.region)

    # Upload content object to S3 bucket
    def upload(self, object: Uploadable):
        self.s3.put_object(Bucket=self.bucket_name, Key=object.key(), Body=object.body(), ServerSideEncryption="AES256")
        return CfnBucketObject(self, object.key())
