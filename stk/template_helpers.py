from __future__ import annotations

from jinja2 import Environment
import re

class TemplateHelpers:
    def __init__(self, custom_helpers):
        self.custom_helpers = custom_helpers

    def inject(self, env: Environment):
        g = env.globals
        g['resourcify'] = self.resourcify

        # Also add custom helpers. We do this after standard ones so templates can
        # override/fix if required
        for helper in self.custom_helpers:
            helper.inject(env, self)

    def resourcify(self, name) -> str:
        return re.sub(r'(\A|\W)+(\w)', lambda m: m.group(2).upper(), str(name))


