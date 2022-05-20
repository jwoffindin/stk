from __future__ import annotations

import boto3
import botocore

from dataclasses import dataclass

from .aws_config import AwsSettings


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
        """
        Return http url for object
        """
        s3_hostname = f"{self.bucket.bucket_name}.s3.{self.bucket.region}.amazonaws.com"
        return "/".join(["https:/", s3_hostname, self.key])

    def as_s3(self) -> str:
        """
        Return s3:// url for object
        """
        return "/".join(["s3:/", self.bucket.bucket_name, self.key])


class CfnBucket:
    FORCE_OVERWRITE = False

    def __init__(self, config: AwsSettings):
        self.bucket_name = config.cfn_bucket
        self.region = config.region
        self.s3 = config.client("s3")

    # Upload content object to S3 bucket
    def upload(self, object: Uploadable, overwrite: bool = False):
        s3 = self.s3

        if self.FORCE_OVERWRITE:
            s3.put_object(Bucket=self.bucket_name, Key=object.key(), Body=object.body(), ServerSideEncryption="AES256")
        else:
            try:
                s3.head_object(Bucket=self.bucket_name, Key=object.key())
                # print(f"Key {object.key()} already exists in {self.bucket_name}, not uploading")
            except botocore.exceptions.ClientError as ex:
                if ex.response["ResponseMetadata"]["HTTPStatusCode"] == 404:
                    s3.put_object(Bucket=self.bucket_name, Key=object.key(), Body=object.body(), ServerSideEncryption="AES256")
                else:
                    raise
        return CfnBucketObject(self, object.key())
