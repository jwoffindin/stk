import os
import pytest

from os import path
from ..config import Config

class ConfigFixtures():
    def fixture_path(self, *dir):
        return path.join(path.dirname(__file__), "fixtures", *dir)

    @pytest.fixture
    def config(self, request):
        return Config('main', environment="test", config_path=self.fixture_path('config', request.param))


@pytest.mark.parametrize('config', ['empty'], indirect=True)
class TestEmptyConfig(ConfigFixtures):
    def test_empty(self, config):
        assert list(config.vars().keys()) == []
        assert list(config.params().keys()) == []

@pytest.mark.parametrize('config', ['simple'], indirect=True)
class TestSimpleConfig(ConfigFixtures):
    def test_simple_load_vars(self, config):
        assert list(config.vars().keys()) == ['foo' ,'bar']
        assert config.var('bar') == 'hello, world!'

    def test_simple_load_params(self, config):
        assert list(config.params().keys()) == ['jane']
        assert config.param('jane') == 'Jane said "hello, world!"'
