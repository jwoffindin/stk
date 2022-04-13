from __future__ import annotations

from . import StackFixtures

from ..config import Config
from ..stack import Stack
from ..template import RenderedTemplate


class TestStackValidation(StackFixtures):
    def test_validate(self, stack, cfn_bucket):
        content_bytes = open(self.fixture_path('templates', 'minimal.yaml'), 'r').read()

        template = RenderedTemplate(name="template.yaml", content=content_bytes)
        assert not stack.validate(template)
