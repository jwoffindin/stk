from __future__ import annotations

import json
import zipfile

from io import BytesIO
from pytest import fixture

from . import StackFixtures
from ..config import Config
from ..provider import GenericProvider
from ..template import RenderedTemplate, TemplateWithConfig
from ..template_helpers import TemplateHelpers
from ..template_source import TemplateSource
from ..cfn_bucket import CfnBucket


class TestTemplateHelpers(StackFixtures):
    @fixture
    def env(self):
        class FakeEnvironment:
            def __init__(self):
                self.globals = dict()
                self.filters = dict()

        return FakeEnvironment()

    @fixture
    def config(self, sts):
        return Config("main", environment="test", config_path=self.fixture_path("custom_helpers", "config"))

    @fixture
    def provider(self):
        p = self.fixture_path("custom_helpers", "templates")
        return TemplateSource(name="main.yaml", root=p).provider()

    def test_custom_helpers_in_config(self, config):
        assert set(config.helpers) == set(["a_custom_helper", "this_one_should_appear_only_once", "another_custom_helper"])

    @fixture
    def basic_helpers(self, provider: GenericProvider, config: Config, env) -> TemplateHelpers:
        return TemplateHelpers(provider=provider, bucket=None, custom_helpers=[], config=config)

    def test_custom_helpers_loaded_from_provider(self, provider: GenericProvider, config: Config, env):
        helpers = TemplateHelpers(provider=provider, bucket=None, custom_helpers=["a_custom_helper"], config=config)

        helpers.inject_helpers(env)

        assert "a_custom_helper" in env.globals
        assert env.globals["a_custom_helper"](41) == 42

    def test_custom_helpers_available_in_template(self, sts, provider: GenericProvider, config: Config, env):
        template = TemplateWithConfig(provider=provider, config=config)

        rendered = template.render()

        assert type(rendered) == RenderedTemplate

        assert rendered["foo_should_be_42"] == "42"
        assert rendered["resourcify"] == "FooBarBaz"

    def test_lambda_uri(self, cfn_bucket, provider, config):
        bucket = CfnBucket(config.aws)
        helpers = TemplateHelpers(provider, bucket=bucket, custom_helpers=[], config=config)

        uri = helpers.lambda_uri("a_function")
        assert uri.startswith("s3://foo/functions/a_function/6fa3f1707cb555571039137d7970816f.zip")

        uri2 = helpers.lambda_uri("a_function")
        assert uri == uri2, "Generated URLs are deterministic"

    def test_upload_zip(self, cfn_bucket, provider, config):
        bucket = CfnBucket(config.aws)
        helpers = TemplateHelpers(provider, bucket=bucket, custom_helpers=[], config=config)

        # Upload our test directory. In contains a single file test.txt
        uri = helpers.upload_zip("files/test", prefix="/opt/foo")

        # Check it has correct url
        assert uri == "files/test/15315fc306560b9eb8332fe277bf8e95.zip"

        # Download file from S3 and check the file is valid ZIP and it contains the
        # expected content
        s3 = config.aws.resource("s3")
        object = s3.Object(cfn_bucket, "files/test/15315fc306560b9eb8332fe277bf8e95.zip")

        content = object.get()["Body"].read()
        fh = BytesIO(content)

        assert "/opt/foo/test.txt" in zipfile.ZipFile(fh, "r").namelist()

    def test_user_data(self, provider, config):
        helpers = TemplateHelpers(provider, bucket=None, custom_helpers=[], config=config)

        parsed = json.loads(helpers.user_data("test1"))

        assert "Fn::Base64" in parsed.keys()

        lines = parsed["Fn::Base64"]["Fn::Join"][1]
        assert "#!/bin/bash\n" in lines
        assert 'Content-Type: text/x-shellscript; charset="utf-8"\n' in lines
        assert {"Ref": "SomeResource"} in lines

    def test_package_ignore(self, provider, config):
        helpers = TemplateHelpers(provider, bucket=None, custom_helpers=[], config=config)

        # The template directory has some .package-ignore files that should be loaded
        ignore = helpers.ignore_list("functions/a_function")
        assert not ignore("foo")
        assert ignore("a")
        assert not ignore("b")
        assert ignore("c")
        assert not ignore("d")

        assert ignore(".package-ignore")
