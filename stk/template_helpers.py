from __future__ import annotations

import re

from jinja2 import Environment
from importlib import util as importutil
from pathlib import Path


class TemplateHelpers:
    def __init__(self, provider: str, custom_helpers: list):
        self.provider = provider
        self.custom_helpers = {}

        for name in custom_helpers:
            self.custom_helpers[name] = self._load_custom_helper(name)

    def inject(self, env: Environment):
        """
        Inject helpers into a Jinja2 environment. We have a set of core (standard) helpers that
        should be useful for most projects.

        Template projects can define custom helpers for domain-specific logic.
        """
        g = env.globals

        # Core helpers
        g['resourcify'] = self.resourcify

        # Custom helpers (defined in templates/helpers and specified in config via 'helpers' stanza)
        for name, func in self.custom_helpers.items():
            # Do this via func to avoid late binding problems
            # https://stackoverflow.com/questions/3431676/creating-functions-in-a-loop
            g[name] = self._make_helper_wrapper(name, func)

    def _make_helper_wrapper(self, name, func):
        return lambda *args, **kwargs: func(self, *args, **kwargs)

    def resourcify(self, name) -> str:
        """
        Given a string with non-alphanumeric characters, maps to a string that can be used as an AWS Resource name.
        """
        return re.sub(r'(\A|\W)+(\w)', lambda m: m.group(2).upper(), str(name))


    def _load_custom_helper(self, name: str):
        """
        TBH I don't really understand this, stolen from stack overflow 😱
        """
        mod_name = f"stk.template_helpers.config.{name}"

        mod_file = str(Path('helpers', name).with_suffix('.py'))
        mod_path = self.provider.cached_path(mod_file)

        spec = importutil.spec_from_file_location(mod_name, mod_path)

        if spec is None:
            raise ImportError(f"Could not load spec for module '{mod_name}' at: {mod_file} ({mod_path})")

        module = importutil.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except FileNotFoundError as e:
            raise ImportError(f"{e.strerror}: {mod_path}") from e

        helper_func = getattr(module, 'helper')

        return helper_func
