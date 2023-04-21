from pytest import fixture

from . import ConfigFixtures
from ..template_source import TemplateSource
from ..template import Template, RenderedTemplate
from ..provider import provider
from ..config import Config


class TestStackRefs(ConfigFixtures):
    @fixture
    def config(self, sts):
        return Config("main", environment="test", config_path=self.fixture_path("deploy-metadata", "config"))

    @fixture
    def provider(self, request):
        source = TemplateSource(name="main", root=self.fixture_path("deploy-metadata", "templates"))
        return provider(source)

    def test_basic_info(self, provider, config):
        t = Template(name="main", provider=provider, helpers=None)
        rendered = t.render(vars=config.vars)
        assert type(rendered) == RenderedTemplate

        assert rendered["Metadata"]["stack"]["deployed_at"].startswith("20")
