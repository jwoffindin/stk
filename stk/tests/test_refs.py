from pyrsistent import v
from pytest import mark, fixture


from . import ConfigFixtures, StackFixtures
from ..config import Config
from ..stack import Stack
from ..template import RenderedTemplate
from ..template_source import TemplateSource
from ..provider import provider


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
        content = open(self.fixture_path("refs", "templates", "outputs.yaml"), "r").read()
        template = RenderedTemplate(name="outputs.yaml", content=content)

        print(template)

        # Create stack from template
        stack = Stack(aws=aws, name="dev-some-other-stack")
        res = stack.create_change_set(template=template, change_set_name="my-changeset-name")
        stack.execute_change_set(action="create", change_set_name="my-changeset-name")
        return stack

    def test_config_parses(self, required_stack, config):
        v = config.refs
        assert v.stack("optional_stack")
        assert v.stack("required_stack")

        # assert v.output("required_stack", "foo") == "bar"
        assert v.output("optional_stack", "foo") == None
        # assert v["required_stack"].required
        # assert v["required_stack"].stack_name == "dev-some-other-stack"
        # assert v["required_stack"]["some_output"] == "output"

        # assert not v["optional_stack"].required
        # assert v["optional_stack"].stack_name == "dev-optional-stack"

    @fixture
    def provider(self, request):
        p = self.fixture_path("refs", "templates")
        source = TemplateSource(name=request.param, version=None, repo=p)
        return provider(source)

    # @mark.parametrize("provider", ["main.yaml"], indirect=True)
    # def test_template_with_refs(self, config: Config, provider):
    #     print(config.vars)
    #     t = TemplateWithConfig(provider=provider, config=config)

    #     rendered = t.render()  # vars={"environment": "test", "result": "okay"})
    #     print(rendered)
    #     assert type(rendered) == RenderedTemplate
