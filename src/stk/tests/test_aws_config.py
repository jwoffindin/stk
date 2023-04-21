import os
import pytest

# pylint: disable=missing-docstring

from . import Fixtures
from ..aws_config import AwsSettings


class TestMinimalAwsConfig(Fixtures):
    def test_minimal(self):
        aws = AwsSettings(region="us-west-2", cfn_bucket="stk-cfn")
        assert aws.region == "us-west-2"
        assert aws.cfn_bucket == "stk-cfn"
