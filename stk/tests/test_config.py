import os
import pytest

# pylint: disable=missing-docstring

from . import ConfigFixtures, StackFixtures
from ..config import Config


@pytest.mark.parametrize("config", ["empty"], indirect=True)
class TestEmptyConfig(ConfigFixtures):
    def test_empty(self, config):
        assert "environment" in config.vars
        assert "name" in config.vars

        assert not list(config.params.keys())


@pytest.mark.parametrize("config", ["simple"], indirect=True)
class TestSimpleConfig(ConfigFixtures):
    def test_simple_load_vars(self, config):
        assert set(config.vars.keys()) >= set(["foo", "bar"])
        assert config.var("bar") == "hello, world!"

    def test_simple_load_params(self, config):
        assert list(config.params.keys()) == ["jane"]
        assert config.param("jane") == 'Jane said "hello, world!"'


@pytest.mark.parametrize("config", ["includes"], indirect=True)
class TestIncludedConfig(ConfigFixtures):
    def test_include_vars(self, config):
        v = config.vars
        assert set(v.keys()) >= set(["a", "b", "c", "d"])

        assert v["a"] == "this is top-level"
        assert v["b"] == "this is from first.yaml"
        assert v["c"] == "this is from second.yaml"
        assert v["d"] == "this is from third.yaml"

    def test_include_params(self, config):
        v = config.params
        assert sorted(v.keys()) == ["p1", "p2", "p3"]

        assert v["p1"] == "this is top-level param"
        assert v["p2"] == "this is param from third.yaml"
        assert v["p3"] == 'interpolated "this is top-level"'


@pytest.mark.parametrize("config", ["environments-simple"], indirect=True)
class TestEnvironmentalPrecdenceConfig(ConfigFixtures):
    def test_var_precedence(self, config):
        v = config.vars
        assert v["a"] == "this is top-level environment - P1"
        assert v["b"] == "this is top-level default - P2"
        assert v["c"] == "this is included environment - P3"
        assert v["d"] == "this is included default - P4"

    def test_param_precedence(self, config):
        v = config.params
        assert v["p1"] == "this is top-level environment param - P1"
        assert v["p2"] == "this is top-level default param - P2"
        assert v["p3"] == "this is included environment param - P3"
        assert v["p4"] == "this is included default param - P4"


@pytest.mark.parametrize("config", ["templates"], indirect=True)
class TestEnvironmentalPrecdenceConfig(ConfigFixtures):
    def test_precedence(self, config):
        source = config.template_source

        assert source.name == "a_template"
        assert source.version == "main"

    def test_shortcut_usage(self, config):
        config = Config("shortcut", environment="test", config_path=self.fixture_path("config", "templates"))

        source = config.template_source

        assert source.name == "b_template"
        assert source.version == "main"


@pytest.mark.parametrize("config", ["tags"], indirect=True)
class TestTags(ConfigFixtures):
    def test_inheritance(self, config):
        tags = config.tags.to_list()

        assert {"Key": "Environment", "Value": "test"} in tags
        assert {"Key": "Product", "Value": "tags-test"} in tags
        assert {"Key": "StackTopLevel", "Value": "some-application"} in tags
        assert {"Key": "StackEnvSpecific", "Value": "True"} in tags


@pytest.mark.parametrize("config", ["core"], indirect=True)
class TestEnvironmentalPrecedenceConfig(ConfigFixtures):
    def test_stack_name(self, config):
        assert config.core.stack_name == "forced-stack-name"

    def test_define_valid_environments(self, config):
        assert config.core.environments == ["dev", "test", "prod"]

    def test_only_valid_environments_allowed(self, config):
        with pytest.raises(Exception) as ex:
            Config("invalid-env", environment="stage", config_path=self.fixture_path("config", "core"))

        assert "invalid-env.yaml defines environments 'stage', which are is listed in core.environments (dev, test, prod)"


@pytest.mark.parametrize("config", ["types"], indirect=True)
class TestInterpolatedDict(ConfigFixtures):
    def test_str(self, config):
        assert config.vars["a_str"] == "hello!"

    def test_int(self, config):
        assert config.vars["an_int"] == 12

    def test_false_preserved(self, config):
        assert config.vars["a_false"] == False

    def test_true_preserved(self, config):
        assert config.vars["a_true"] == True

    def test_none_preserved(self, config):
        assert config.vars["a_none"] == None
        assert config.vars["no_value"] == None


@pytest.mark.parametrize("config", ["simple"], indirect=True)
class TestSimpleConfig(ConfigFixtures):
    def test_simple_load_vars(self, config):
        assert set(config.vars.keys()) >= set(["foo", "bar"])
        assert config.var("bar") == "hello, world!"

    def test_simple_load_params(self, config):
        assert list(config.params.keys()) == ["jane"]
        assert config.param("jane") == 'Jane said "hello, world!"'


@pytest.mark.parametrize("config", ["simple"], indirect=True)
class TestSimpleConfig(ConfigFixtures):
    def test_aws_vars(self, config, aws, sts):
        assert config.vars["account_id"] == 123456789012
