# pylint: disable=missing-docstring

import json

from pytest import fixture, raises, mark
from botocore.stub import Stubber

from . import ConfigFixtures, StackFixtures
from ..config import Config
from ..stack import Stack
from ..template import RenderedTemplate

@mark.skip("moto outputs seem to be broken at the moment")
class TestStackRefs(ConfigFixtures, StackFixtures):
    @fixture
    def config(self, sts):
        return Config("main", environment="dev", config_path=self.fixture_path("refs", "config"))

    @fixture
    def required_stack(self, cloudformation, cfn_bucket, aws):
        """
        Create dev-some-other-stack from fixtures/refs/templates/outputs.yaml
        """

        # Render template
        template = RenderedTemplate(name="outputs.yaml", content=open(self.fixture_path("refs", "templates", "outputs.yaml"), "r").read())

        # Create stack from template
        stack = Stack(aws=aws, name="dev-some-other-stack")
        result = stack.create_change_set(template=template).execute()
        return stack

    def test_config_parses(self, required_stack, config):
        refs = config.refs
        assert not refs.stack("optional_stack").exists()
        assert refs.stack("required_stack").exists()
        assert refs.output("optional_stack", "foo") == None

        assert not refs.exists("optional_stack")
        assert refs.exists("required_stack")

    def test_stack_not_defined(self, config):
        v = Config.StackRefs(stack_refs={}, config=config)
        with raises(Exception, match="Attempt to access stack foo, but it's not defined in config.refs"):
            v.stack("foo")

    def test_stack_not_exists_with_defaults(self, config, cloudformation):
        v = Config.StackRefs(stack_refs={"foo": None}, config=config)
        with raises(Exception, match="Stack config.refs\[foo\] \(dev-foo\) does not exist, but is required"):
            v.output("foo", "bar")

    def test_stack_not_exists_with_name(self, config, cloudformation):
        v = Config.StackRefs(stack_refs={"foo": {"stack_name": "something-{{ environment }}-else"}}, config=config)
        with raises(Exception, match="Stack config.refs\[foo\] \(something-dev-else\) does not exist, but is required"):
            v.output("foo", "bar")

    def test_multiple_required_stacks_not_exists(self, config, cloudformation):
        refs = Config.StackRefs(stack_refs={"foo": {"stack_name": "something-{{ environment }}-else"}, "bar": None, "buz": {}}, config=config)

        assert not refs.stack("foo").exists()
        assert not refs.stack("bar").exists()
        assert not refs.stack("buz").exists()

        with raises(Exception, match="Stack config.refs\[foo\] \(something-dev-else\) does not exist, but is required"):
            refs.output("foo", "some_output")

        with raises(Exception, match="Stack config.refs\[bar\] \(dev-bar\) does not exist, but is required"):
            refs.output("bar", "some_output")

    def test_invalid_stack_ref(self, config, cloudformation):
        refs = Config.StackRefs(
            stack_refs={
                "foo": {"stack_name": "something-{{ environment }}-else"},
                "optional": True,
            },
            config=config,
        )

        with raises(SystemExit, match="-1"):
            refs.output("foo", "some_output")

    def test_optional_stacks_not_exists(self, config, cloudformation):
        refs = Config.StackRefs(
            stack_refs={
                "foo": {"stack_name": "something-{{ environment }}-else", "optional": True},
                "bar": {"stack_name": "something-{{ environment }}-else", "optional": "true"},
            },
            config=config,
        )

        assert refs.output("foo", "imaginary_output") == None
        assert refs.output("bar", "imaginary_output") == None

    def test_stack_exist_no_output(self, config, required_stack):
        refs = Config.StackRefs(stack_refs={"some-other-stack": None}, config=config)

        with raises(KeyError, match="'unknown_output not in outputs of dev-some-other-stack"):
            refs.output("some-other-stack", "unknown_output")

    def create_cfn_mock_response(self, refs):
        # refs.stacks()
        for name in refs.stacks().keys():
            # mock the cfn client
            stubber = Stubber(refs[name].cfn)
            expected_params = {"StackName": f"dev-{name}"}
            response = json.loads(self.fixture_content("mock-describe-stacks-response.json"))
            stubber.add_response("describe_stacks", response, expected_params)

            return stubber

    def test_output_not_exists(self, config, cloudformation):
        """
        Accessing a non-existant output on a stack will raise an exception
        """
        refs = Config.StackRefs(stack_refs={"some-other-stack": None}, config=config)
        stubber = self.create_cfn_mock_response(refs)
        with stubber:
            with raises(Exception, match="AnOutput not in outputs of dev-some-other-stack - only have \['MyOutput'\]"):
                refs.output("some-other-stack", "AnOutput")

    def test_output_exist(self, config, cloudformation):
        """
        Referencing an output that *does* exist will actually return the value :-)
        """
        refs = Config.StackRefs(stack_refs={"some-other-stack": None}, config=config)
        stubber = self.create_cfn_mock_response(refs)
        with stubber:
            output = refs.output("some-other-stack", "MyOutput")
            assert output == "An Output Value"
            assert output.description == "Some description"
