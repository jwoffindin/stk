# pylint: disable=missing-docstring

from os import path, environ

import boto3
from pytest import fixture
from pytest import fixture
from moto import mock_s3, mock_cloudformation, mock_sts


from ..aws_config import AwsSettings
from ..config import Config, ConfigFile
from ..stack import Stack


class Fixtures:
    def fixture_path(self, *dir):
        return path.join(path.dirname(__file__), "fixtures", *dir)

    def fixture_content(self, *dir) -> bytes:
        return open(self.fixture_path(*dir), "rb").read()


class StackFixtures(Fixtures):
    @fixture
    def aws(self):
        """Mocked AWS Credentials for moto."""
        environ["AWS_ACCESS_KEY_ID"] = "testing"
        environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        environ["AWS_SECURITY_TOKEN"] = "testing"
        environ["AWS_SESSION_TOKEN"] = "testing"
        return AwsSettings(region="us-east-1", cfn_bucket="foo")

    @fixture
    def sts(self, aws):
        with mock_sts():
            conn = boto3.client("sts", region_name="us-east-1")
            yield conn

    @fixture
    def s3(self, aws, sts):
        with mock_s3():
            conn = boto3.client("s3", region_name="us-east-1")
            yield conn

    @fixture
    def cloudformation(self, aws, sts):
        with mock_cloudformation():
            conn = boto3.client("cloudformation", region_name="us-east-1")
            yield conn

    @fixture
    def cfn_bucket(self, s3):
        bucket_name = "foo"
        s3.create_bucket(Bucket=bucket_name)
        yield bucket_name

    @fixture
    def stack(self, cloudformation, s3, aws):
        yield Stack(aws=aws, name="test-stack")


class ConfigFixtures(StackFixtures):
    @fixture
    def config(self, request, sts):
        return Config("main", environment="test", config_path=self.fixture_path("config", request.param))

    @fixture
    def config_file(self, request, sts):
        return ConfigFile("main.yaml", self.fixture_path("config", request.param))
