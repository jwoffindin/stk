# pylint: disable=missing-docstring

import pytest

from pytest import fixture, mark
from click.testing import CliRunner

from . import StackFixtures
from ..cli import stk
from ..template import Template


class CliFixtures(StackFixtures):
    @fixture
    def args(self, request, s3, cloudformation, cfn_bucket):
        config_path = self.fixture_path("cli", "config")
        template_path = self.fixture_path("cli", "templates")
        command = request.param.pop(0)
        return [command, *request.param, "--config-path", config_path, "--template-path", template_path]

    @fixture
    def cli(self, args):
        return CliRunner().invoke(stk, args)


class TestCliShowTemplate(CliFixtures, StackFixtures):
    @mark.parametrize("args", [["show-template", "basic", "test"]], indirect=True)
    def test_show_basic_template(self, cli):
        assert "This is a sample template for test environment" in cli.output
        assert 'TopicName: "a_topic"' in cli.output
        assert cli.exit_code == 0

    @mark.parametrize("args", [["show-template", "different-template-name", "test"]], indirect=True)
    def test_show_failed_template(self, cli):
        assert 'TopicName: "another_topic"' in cli.output
        assert cli.exit_code == 0


class TestCliValidateTemplate(CliFixtures):
    @mark.parametrize("args", [["validate", "basic", "test"]], indirect=True)
    @mark.skip("I think this should be a valid test")
    def test_validate_basic_template(self, cli):
        assert "Template is ok" in cli.output
        assert cli.exit_code == 0

    @mark.parametrize("args", [["validate", "invalid", "test"]], indirect=True)
    def test_invalid_yaml_template(self, args):
        cli = CliRunner().invoke(stk, args, catch_exceptions=False)

        assert "Template is NOT ok" in cli.output
        assert cli.exit_code == -1


# class TestCliCreate(CliFixtures):
#     @mark.parametrize('args', [['create', 'basic', 'test']], indirect=True)
#     def test_create_stack(self, cli):
#         assert 'Creating stack test-basic' in cli.output
#         assert 'Stack created successfully' in cli.output
#         assert cli.exit_code == 0


class TestCliCreateChangeSet(CliFixtures):
    @mark.parametrize("args", [["create-change-set", "basic", "test", "my-change-set"]], indirect=True)
    def test_create_change_set(self, cli):
        assert "Creating change set my-change-set for test-basic" in cli.output
        assert "Change set created" in cli.output
        assert cli.exit_code == 0
