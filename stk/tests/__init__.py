import pytest
from os import path
from ..config import Config, ConfigFile

class ConfigFixtures():
    def fixture_path(self, *dir):
        return path.join(path.dirname(__file__), "fixtures", *dir)

    @pytest.fixture
    def config(self, request):
        return Config('main', environment="test", config_path=self.fixture_path('config', request.param))

    @pytest.fixture
    def config_file(self, request):
        return ConfigFile('main.yml', self.fixture_path('config', request.param))
