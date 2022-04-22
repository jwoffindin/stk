from __future__ import annotations
import boto3

from botocore.exceptions import ClientError

from .aws_config import AwsSettings
from .cfn_bucket import CfnBucket


class BasicStack:
    def __init__(self, aws: AwsSettings, name: str):
        self.aws = aws
        self.name = name
        self.cfn = boto3.client("cloudformation", region_name=self.aws.region)
        self.bucket = CfnBucket(aws)

    def exists(self):
        return self.status() != None

    def status(self):
        stack = self.describe_stack()
        if stack:
            return stack["StackStatus"]

    def outputs(self) -> dict:
        if not hasattr(self, "__outputs"):
            self.__outputs = self.__get_outputs()
        return self.__outputs

    def output(self, key) -> str:
        outputs = self.outputs()
        if outputs:
            if key in outputs:
                return outputs[key]
            raise KeyError(f"{key} not in outputs of {self.name} - only have {list(outputs.keys())}")

    def describe_stack(self):
        try:
            stack = self.cfn.describe_stacks(StackName=self.name)["Stacks"][0]
            # self._id = stack["StackId"]

            assert self.name in [stack["StackId"], stack["StackName"]]
            return stack
        except ClientError as e:
            err = e.response["Error"]
            if (err["Code"] == "ValidationError") and ("does not exist" in err["Message"]):
                return None
            raise (e)

    # def identifier(self):
    #     """
    #     Return stack ARN
    #     """
    #     if not hasattr(self, "_id"):
    #         self.describe_stack()  # side-effect is to set ID - if stack exists
    #     return self._id

    def __get_outputs(self) -> dict:
        stack = self.describe_stack()
        if not stack:
            return None

        ret_val = {}
        for output in stack["Outputs"]:
            ret_val[output["OutputKey"]] = output["OutputValue"]
        return ret_val
