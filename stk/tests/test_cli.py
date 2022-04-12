from pytest import fixture, mark
from click.testing import CliRunner

from . import Fixtures
from ..cli import stk

class TestCliShowTemplate(Fixtures):

    @fixture
    def cli(self, request):
        config_path = self.fixture_path('cli', 'config')
        template_path = self.fixture_path('cli', 'templates')

        args = ['show-template', '--config-path', config_path, '--template-path', template_path, *request.param]

        return CliRunner().invoke(stk, args)

    @mark.parametrize('cli', [['basic', 'test']], indirect=True)
    def test_show_basic_template(self, cli):
        assert 'This is a sample template for test environment' in cli.output
        assert 'Fuzziness: "maximum"' in cli.output
        assert cli.exit_code == 0

    @mark.parametrize('cli', [['different_template_name', 'test']], indirect=True)
    def test_show_failed_template(self, cli):
        assert 'Fuzziness: "uncanny"' in cli.output
        assert cli.exit_code == 0

