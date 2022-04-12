import os
import pytest


from . import ConfigFixtures

@pytest.mark.parametrize('config', ['empty'], indirect=True)
class TestEmptyConfig(ConfigFixtures):
    def test_empty(self, config):
        assert list(config.vars.keys()) == ['environment']
        assert list(config.params.keys()) == []

@pytest.mark.parametrize('config', ['simple'], indirect=True)
class TestSimpleConfig(ConfigFixtures):
    def test_simple_load_vars(self, config):
        assert list(config.vars.keys()) == ['environment', 'foo' ,'bar']
        assert config.var('bar') == 'hello, world!'

    def test_simple_load_params(self, config):
        assert list(config.params.keys()) == ['jane']
        assert config.param('jane') == 'Jane said "hello, world!"'

@pytest.mark.parametrize('config', ['includes'], indirect=True)
class TestIncludedConfig(ConfigFixtures):
    def test_include_vars(self, config):
        v = config.vars
        assert sorted(v.keys()) == ['a', 'b', 'c', 'd', 'environment']

        assert v['a'] == 'this is top-level'
        assert v['b'] == 'this is from first.yaml'
        assert v['c'] == 'this is from second.yaml'
        assert v['d'] == 'this is from third.yaml'

    def test_include_params(self, config):
        v = config.params
        assert sorted(v.keys()) == ['p1', 'p2', 'p3']

        assert v['p1'] == 'this is top-level param'
        assert v['p2'] == 'this is param from third.yaml'
        assert v['p3'] == 'interpolated "this is top-level"'


@pytest.mark.parametrize('config', ['environments-simple'], indirect=True)
class TestEnvironmentalPrecdenceConfig(ConfigFixtures):
    def test_var_precedence(self, config):
        v = config.vars
        assert v['a'] == 'this is top-level environment - P1'
        assert v['b'] == 'this is top-level default - P2'
        assert v['c'] == 'this is included environment - P3'
        assert v['d'] == 'this is included default - P4'

    def test_param_precedence(self, config):
        v = config.params
        assert v['p1'] == 'this is top-level environment param - P1'
        assert v['p2'] == 'this is top-level default param - P2'
        assert v['p3'] == 'this is included environment param - P3'
        assert v['p4'] == 'this is included default param - P4'

@pytest.mark.parametrize('config', ['templates'], indirect=True)
class TestEnvironmentalPrecdenceConfig(ConfigFixtures):
    def test_precedence(self, config):
        source = config.template_source

        assert source.name == 'a_template'
        assert source.version == 'main'
