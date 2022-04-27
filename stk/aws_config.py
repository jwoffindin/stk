from dataclasses import dataclass

import boto3


@dataclass
class AwsSettings:
    region: str
    cfn_bucket: str
    account_id: str = None

    def client(self, service):
        client = boto3.client(service, region_name=self.region)

        if self.account_id:
            sts = boto3.client("sts")
            account_id = sts.get_caller_identity()["Account"]
            if str(account_id) != str(self.account_id):
                raise Exception(f"Incorrect AWS Account - exected {self.account_id}, but appear to be using {account_id} ")

        return client
