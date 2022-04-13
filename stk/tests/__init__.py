import boto3

from os import path, environ
from pytest import fixture
from pytest import fixture
from moto import mock_s3, mock_cloudformation

from ..config import Config, ConfigFile
from ..stack import Stack

class Fixtures():
    def fixture_path(self, *dir):
        return path.join(path.dirname(__file__), "fixtures", *dir)

class ConfigFixtures(Fixtures):
    @fixture
    def config(self, request):
        return Config('main', environment="test", config_path=self.fixture_path('config', request.param))

    @fixture
    def config_file(self, request):
        return ConfigFile('main.yaml', self.fixture_path('config', request.param))

class StackFixtures(Fixtures):
    @fixture
    def aws(self):
        """Mocked AWS Credentials for moto."""
        environ["AWS_ACCESS_KEY_ID"] = "testing"
        environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        environ["AWS_SECURITY_TOKEN"] = "testing"
        environ["AWS_SESSION_TOKEN"] = "testing"

    @fixture
    def s3(self, aws):
        with mock_s3():
            conn = boto3.client("s3", region_name="us-east-1")
            yield conn

    @fixture
    def cloudformation(self, aws):
        with mock_cloudformation():
            conn = boto3.client("cloudformation", region_name="us-east-1")
            yield conn

    @fixture
    def cfn_bucket(self, s3):
        bucket_name = "foo"
        s3.create_bucket(Bucket=bucket_name)
        yield bucket_name

    @fixture
    def stack(self, cloudformation, s3):
        aws_settings = Config.AwsSettings(region="us-east-1")
        yield Stack(aws=aws_settings, name="test-stack")
