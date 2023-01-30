from __future__ import annotations
from typing import Dict, Union

from botocore.exceptions import ClientError

from . import log
from .aws_config import AwsSettings
from .cfn_bucket import CfnBucket

class BasicStack:
    def __init__(self, aws: AwsSettings, name: str):
        self.aws = aws
        self.name = name
        self.cfn = aws.client("cloudformation")
        self.bucket = CfnBucket(aws)

    def exists(self):
        """Tests if stack with .name exists"""
        return self.status() != None

    def status(self):
        """Returns stack status, or None if stack does not exist"""
        stack = self.describe_stack()
        if stack:
            return stack["StackStatus"]

    def outputs(self) -> Union[Dict[str, BasicStack.Output], None]:
        """Return all outputs for a stack"""
        if not hasattr(self, "__outputs"):
            self.__outputs = self.__get_outputs()
        return self.__outputs

    def output(self, key) -> str:
        """Return value of named key, raising KeyError if no matching output found"""
        log.info("Getting output %s from %s", key, self.name)
        outputs = self.outputs()

        if key in outputs:
            return outputs[key]
        raise KeyError(f"{key} not in outputs of {self.name} - only have {list(outputs.keys())}")

    def describe_stack(self):
        """Perform a describe_stack operation against stack, returning None if it doesn't exist"""
        try:
            stack = self.cfn.describe_stacks(StackName=self.name)["Stacks"][0]
            assert self.name in [stack["StackId"], stack["StackName"]]
            return stack
        except ClientError as exc:
            err = exc.response["Error"]
            if (err["Code"] == "ValidationError") and ("does not exist" in err["Message"]):
                return None
            raise exc

    class Output(str):
        """
        A stack output can have a description (and other attributes). We are normally interested in just the
        value when querying the output, but the description is also available via an attribute

        output = stack.output('Foo')
        print("output description is " + output.description)

        """
        def __new__(cls, value: str, description: str):
            obj = str.__new__(cls, value)
            obj.description = description
            return obj

    def __get_outputs(self) -> Union[Dict[str, BasicStack.Output], None]:
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
