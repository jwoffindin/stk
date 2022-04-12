from dataclasses import dataclass
from importlib import util as importutil
from pathlib import Path
from typing import Any

@dataclass
class TemplateHelperLoader:
    provider: Any
    namespace: str

    @dataclass
    class TemplateHelper:
        name: str
        impl: Any

        def inject(self, env: str, context: Any):
            def wrapper_func(*args, **kwargs):
                return self.impl(context, *args, **kwargs)
            env.globals[self.name] = wrapper_func

    def load_helpers(self, names: list):
        helpers = []

        for name in names:
            helper = self._load(name)
            helpers.append(self.TemplateHelper(name, helper))

        return helpers

    def _load(self, name: str):
        mod_name = f"stk.template_helpers.{self.namespace}.{name}"
        print(f"mod_name={mod_name}")

        mod_file = str(Path('helpers', name).with_suffix('.py'))
        mod_path = self.provider.cached_path(mod_file)
        print(f"mod_path={mod_path}")

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

