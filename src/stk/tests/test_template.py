from pytest import fixture, mark

from . import Fixtures
from ..template import RenderedTemplate, Template, FailedTemplate
from ..template_source import TemplateSource
from ..provider import provider


class TestTemplate(Fixtures):
    @fixture
    def provider(self, request):
        p = self.fixture_path("templates", "simple")
        source = TemplateSource(name=request.param, root=p)
        return provider(source)

    @mark.parametrize("provider", ["main.yaml"], indirect=True)
    def test_render_simple_template(self, provider):
        """
        The Template().render method returns a RenderedTemplate. The rendered template may
        have
        """
        t = Template(name="test", provider=provider, helpers=None)

        rendered = t.render(vars={"environment": "test", "result": "okay"})

        assert type(rendered) == RenderedTemplate

        # Rendered template acts like a dict for parsed template (assuming successfully parsed)
        assert rendered["template_version"] == 1.0
        assert rendered["interpolated"] == "Environment test is okay"

        assert "should_be_excluded" not in rendered

        assert "item_0" in rendered
        assert "item_1" in rendered
        assert "item_2" in rendered

        # str() method returns parsed template
        assert "interpolated: 'Environment test is okay'" in str(rendered)

    @mark.parametrize("provider", ["main.yaml"], indirect=True)
    def test_render_jinja_error_handling(self, provider):
        t = Template(provider=provider, custom_helpers=[])

        rendered = t.render(vars={})

        assert type(rendered) == FailedTemplate
        assert rendered.error
        assert "template_version: 1.0" in rendered.source

        # Not overly happy about overriding the 'str()' method to render an error
        as_str = str(rendered)

        assert "'environment' is undefined" in as_str
        assert "main.yaml at line 3" in as_str

    @mark.parametrize("provider", ["invalid.yaml"], indirect=True)
    def test_render_jinja_error_handling(self, provider):
        t = Template(name="test_template", provider=provider)

        rendered = t.render(vars={"environment": "test"})

        assert type(rendered) == FailedTemplate
        assert "Error occurred outsite of template" in str(rendered)

    @mark.parametrize("provider", ["quoted.yaml"], indirect=True)
    def test_render_quoted_template(self, provider):
        t = Template(name="quoted", provider=provider, helpers=None)

        rendered = t.render(vars={})

        assert "value: ['hello', 'there']" in str(rendered)
