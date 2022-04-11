import os
import pytest

from os import path
from ..config import Config

class TestConfig():
  def fixture_path(self, *dir):
    return path.join(path.dirname(__file__), "fixtures", *dir)

  def test_empty(self):
    c = Config(name="empty", environment="foo", config_path=self.fixture_path('config'))
    assert list(c.vars().keys()) == []
    assert list(c.params().keys()) == []

  def test_load(self):
    c = Config(name="simple", environment="foo", config_path=self.fixture_path('config'))

    assert list(c.vars().keys()) == ['foo']
    assert list(c.params().keys()) == ['jane']

