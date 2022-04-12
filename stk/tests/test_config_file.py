import os
import pytest


from . import ConfigFixtures

@pytest.mark.parametrize('config_file', ['includes'], indirect=True)
class TestConfigFile(ConfigFixtures):
    def test_included_mapped(self, config_file):
        assert config_file.includes() == ['includes/first.yaml']

    def test_load_configs(self, config_file):
        configs = config_file.load_includes()

        assert ['main.yml', 'includes/first.yaml', 'includes/third.yaml', 'includes/second.yaml'] == list(c.filename for c in configs)

    def test_environments(self, config_file):
        assert config_file.environments() == ['dev', 'test', 'prod']