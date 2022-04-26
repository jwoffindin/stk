from pyrsistent import v
from pytest import mark, fixture


from . import ConfigFixtures, StackFixtures
from ..config import Config
from ..stack import Stack
from ..template import RenderedTemplate
from ..template_source import TemplateSource


class TestStackRefs(ConfigFixtures, StackFixtures):
    @fixture
    def config(self):
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
        stack.create_change_set(template=template).execute()
        return stack

    def test_config_parses(self, required_stack, config):
        v = config.refs
        assert not v.stack("optional_stack").exists()
        assert v.stack("required_stack").exists()

        # Pending - moto doesn't seem to do outputs
        # assert v.output("optional_stack", "foo") == None
