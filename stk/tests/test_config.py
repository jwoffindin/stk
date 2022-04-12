import os
import pytest


from . import ConfigFixtures

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
# @pytest.mark.parametrize('config', ['includes'], indirect=True)
# class TestIncludedConfig(ConfigFixtures):
#     def test_include_vars(self, config):
#         v = config.vars()
#         assert list(v.keys()) == ['a', 'b', 'c', 'd']

#         assert v['a'] == 'this is top-level'
#         assert v['b'] == 'this is first include that should override second include'
#         assert v['c'] == 'this is from second.yaml'
#         assert v['d'] == 'this is from third.yaml'
