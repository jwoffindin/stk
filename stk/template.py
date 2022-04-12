from __future__ import annotations
from cfn_tools import load_yaml
from jinja2 import Environment, StrictUndefined

from .provider import GenericProvider
from .template_helper_loader import TemplateHelperLoader
from .config import Config
from .template_helpers import TemplateHelpers
class FailedTemplate(dict):
    ERROR_CONTEXT_LINES = 3

    def __init__(self, source: str, location: str = 'unknown', error: Exception = None):
        self.source = source
        self.location = location
        self.error = error

    def __str__(self) -> str:
        """
        Return traceback showing location in template that triggered the exception
        """
        traceback = self.error.__traceback__
        last_frame = traceback
        while traceback:
            filename = traceback.tb_frame.f_code.co_filename
            if filename == '<template>':
                break
            last_frame = traceback
            traceback = traceback.tb_next

        # If don't find filename == <template> then exception likely triggered by something
        # outside of template.
        if not traceback:
            line_no = last_frame.tb_lineno
            filename = last_frame.tb_frame.f_code.co_filename
            return f"Error occurred outsite of template\n{str(self.error)}\n{filename}:{line_no}"

        line_no = traceback.tb_lineno
        return f'{str(self.error)}\n{self.location} at line {line_no}:\n\n{self.source_context(line_no)}\n\n'

    def source_context(self, line_no: int) -> str:
        lines = self.source.split("\n")

        from_line = max(1, line_no - self.ERROR_CONTEXT_LINES)
        to_line = min(len(lines), line_no + self.ERROR_CONTEXT_LINES) - 1

        code = []
        for i in range(from_line, to_line):
            code.append("%4d : %s" % (i, lines[i-1]))
        return "\n".join(code)

class RenderedTemplate(dict):
    def __init__(self, content: str):
        self.content = content

        parsed = load_yaml(content)
        if parsed:
            self.update(parsed)

    def __str__(self) -> str:
        return self.content


class Template:
    def __init__(self, provider: GenericProvider, helpers: TemplateHelpers = None):
        self.provider = provider
        self.helpers  = helpers

    def render(self, vars: dict) -> str:
        raw_template = str(self.provider.template(), 'utf-8')

        content = None
        env = Environment(line_statement_prefix="##", undefined=StrictUndefined)

        if self.helpers:
            self.helpers.inject(env)

        # This will fail if rendered template can't be processed via Jinja2 (e.g. undefined variable access etc)
        try:
            content = env.from_string(source=raw_template).render(vars)
        except Exception as ex:
            return FailedTemplate(source=raw_template, location=str(self.provider), error=ex)

        # This will fail if rendered template can not be parsed as value YAML
        try:
            return RenderedTemplate(content=content)
        except Exception as ex:
            return FailedTemplate(source=content, location=str(self.provider), error=ex)


class TemplateWithConfig(Template):
    def __init__(self, provider: GenericProvider, config: Config):
        self.vars = config.vars

        loader = TemplateHelperLoader(provider=provider, namespace="config")

        custom_helpers = loader.load_helpers(config.helpers)

        helpers = TemplateHelpers(custom_helpers=custom_helpers)

        super().__init__(provider, helpers=helpers)

    def render(self) -> str:
        return super().render(self.vars)