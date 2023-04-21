"""
Provides TemplateCommand
"""

from . import console
from .change_set import ChangeSet
from .stack_delegated_command import StackDelegatedCommand
from .template import TemplateWithConfig


class TemplateCommand(StackDelegatedCommand):
    """
    Command that applies a template to a stack
    """

    def __post_init__(self):
        super().__post_init__()
        self.template = TemplateWithConfig(
            provider=self.config.template_source.provider(), config=self.config).render()

        parse_error = self.template.error
        if parse_error:
            console.log(
                f":x: Template is NOT ok - {parse_error}", emoji=True, style="red")
            console.print(str(self.template))
            exit(-1)

    def validate(self):
        """
        Validate template by parsing it (using provided config) and applies
        AWS CFN validation.
        """
        template = self.template
        if not template.error:
            errors = self.stack.validate(template)
            if errors:
                console.print(str(self.template))
                console.log(f"{errors}\n\n", style="red", markup=False)
                console.log(
                    ":x: Template is NOT ok - failed validation", emoji=True, style="red")
                exit(-1)
            else:
                console.log(":+1: Template is ok", emoji=True, style="green")

    def create_change_set(self, change_set_name=None) -> ChangeSet:
        """
        Create a change set
        """
        with console.status("Creating change set"):
            tags = self.config.tags.to_list()
            params = self.config.params
            cs = self.stack.create_change_set(
                template=self.template,
                tags=tags,
                change_set_name=change_set_name,
                params=params
            )
        return cs
