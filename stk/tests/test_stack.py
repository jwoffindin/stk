from __future__ import annotations

from pytest import fixture

from . import StackFixtures

from ..stack import StackException
from ..template import RenderedTemplate


class TestStack(StackFixtures):
    @fixture
    def rendered_template(self, cfn_bucket):
        content_bytes = open(self.fixture_path("templates", "minimal.yaml"), "r").read()
        return RenderedTemplate(name="template.yaml", content=content_bytes)

    def test_stack_exception(self, stack):
        StackException(stack, "This is a test exception")

    def test_validate(self, stack, rendered_template):
        assert not stack.validate(rendered_template)

    def test_new_stack_create_change_set_valid(self, stack, rendered_template):
        res = stack.create_change_set(template=rendered_template, change_set_name="my-changeset-name")
        assert res.available()

        execute_res = stack.execute_change_set(change_set_name="my-changeset-name")
        assert execute_res
