from __future__ import annotations

import os
import logging

from botocore.exceptions import ClientError

from .aws_config import AwsSettings
from .cfn_bucket import CfnBucket

logging.basicConfig(filename="stk.log", filemode="w", level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("basic_stack")


class BasicStack:
    def __init__(self, aws: AwsSettings, name: str):
        self.aws = aws
        self.name = name
        self.cfn = aws.client("cloudformation")
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
        log.info(f"Getting output {key} from {self.name}")
        outputs = self.outputs()

        if key in outputs:
            return outputs[key]
        raise KeyError(f"{key} not in outputs of {self.name} - only have {list(outputs.keys())}")

    def describe_stack(self):
        try:
            stack = self.cfn.describe_stacks(StackName=self.name)["Stacks"][0]
            assert self.name in [stack["StackId"], stack["StackName"]]
            return stack
        except ClientError as e:
            err = e.response["Error"]
            if (err["Code"] == "ValidationError") and ("does not exist" in err["Message"]):
                return None
            raise (e)

    class Output(str):
        def __new__(cls, value: str, description: str):
            obj = str.__new__(cls, value)
            obj.description = description
            return obj

    def __get_outputs(self) -> dict:
        stack = self.describe_stack()
        if not stack:
            return None

        if "Outputs" not in stack:
            return None

        ret_val = {}
        for output in stack["Outputs"]:
            description = ""
            if "Description" in output:
                description = output["Description"]
            ret_val[output["OutputKey"]] = self.Output(output["OutputValue"], description)
        return ret_val


class StackReference(BasicStack):
    def status(self):
        if not hasattr(self, "_status"):
            self._status = super().status()
        return self._status
