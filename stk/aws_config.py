from dataclasses import dataclass


@dataclass
class AwsSettings:
    region: str
    cfn_bucket: str
    account_id: str = None
