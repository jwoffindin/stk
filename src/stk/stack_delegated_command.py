"""
Base class for commands that work against a deployed/deployable stack
"""
import json
from typing import List
from dataclasses import dataclass
from rich.table import Table

import yaml
from . import console
from .stack import Stack
from .config import Config
from .util import parse_overrides

@dataclass
class StackDelegatedCommand:
    """
    Base class for commands that work against a deployed/deployable stack
    """
    name: str
    environment: str
    config_path: str
    template_path: str
    var: List
    param: List
    overrides: str
    outputs_format: str = "table"

    def __post_init__(self):
        overrides = parse_overrides(self.var, self.param, self.overrides)
        self.config = Config(
            name=self.name,
            environment=self.environment,
            config_path=self.config_path,
            template_path=self.template_path,
            overrides=overrides
        )
        self.stack = Stack(aws=self.config.aws,
                           name=self.config.core.stack_name)
        self.stack_name = self.stack.name

    def __getattr__(self, name):
        if hasattr(self.stack, name):
            return getattr(self.stack, name)
        return super().__getattr__(name)

    def show_outputs(self):
        """
        Display a table of outputs for a CFN stack
        """
        stack_outputs = self.outputs()
        if stack_outputs:
            if self.outputs_format == 'table':
                t = Table("Key", "Value", "Description", title="Stack Outputs",
                        title_justify="left", title_style="bold")
                for key in sorted(stack_outputs.keys()):
                    value = stack_outputs[key]
                    t.add_row(key, value, value.description)
                console.print(t)
            elif self.outputs_format == 'json':
                print(json.dumps(stack_outputs))
            elif self.outputs_format == 'yaml':
                print(yaml.dump({ k: str(v) for k, v in stack_outputs.items() }))
            else:
                raise ValueError(f"invalid output format {self.outputs_format}")
        else:
            console.print(f"Stack {self.stack_name} does not have any outputs")
