from __future__ import annotations

import hashlib
import re
import logging

from typing import List
from cfn_tools import load_yaml
from jinja2 import Environment, StrictUndefined

from .provider import GenericProvider
from .config import Config
from .template_helpers import TemplateHelpers
from .cfn_bucket import CfnBucket, Uploadable

log = logging.getLogger("template")


class FailedTemplate(dict):
    ERROR_CONTEXT_LINES = 3

    def __init__(self, name: str, source: str, location: str = "unknown", error: Exception = None):
        self.name = name
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
            if filename == "<template>" or filename == "<unknown>":
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
        return f"{str(self.error)}\n{self.location} at line {line_no}:\n\n{self.source_context(line_no)}\n\n"

    def source_context(self, line_no: int) -> str:
        lines = self.source.split("\n")

        from_line = max(1, line_no - self.ERROR_CONTEXT_LINES)
        to_line = min(len(lines), line_no + self.ERROR_CONTEXT_LINES + 1)

        code = []
        for i in range(from_line, to_line):
            line = "%4d : %s" % (i, lines[i - 1])
            if i == line_no:
                line = f"[bold red]{line}[/bold red]"
            code.append(line)
        return "\n".join(code)


class RenderedTemplate(dict, Uploadable):
    def __init__(self, name: str, content: str):
        self.content = content
        self.name = name
        self.error = None  # enables if Template().render().error:...

        parsed = load_yaml(content)
        if not hasattr(parsed, "keys"):
            raise Exception(f"Template result is a {type(parsed)}, expected dict")
        self.update(parsed)

    def __str__(self) -> str:
        return self.content

    def md5(self) -> str:
        return hashlib.md5(self.body()).hexdigest()

    def body(self) -> bytes:
        return self.content.encode("utf-8")

    def key(self) -> str:
        return "/".join(["templates", self.name, self.md5() + ".zip"])

    def iam_capabilities(self) -> List[str]:
        """
        Stacks are decorated with iam capability requirements. Can either do:

            # deprecated
            Metadata:
                iam_capabilities: [....]

        or:

            Metadata:
                stack:
                    iam_capabilities: [....]

        """
        metadata = self.get("Metadata", {})
        if "iam_capabilities" in metadata:
            log.warning("Metadata.iam_capabilities is deprecated. Use Metadata.stack.iam_capabilities instead")
            return metadata.get("iam_capabilities", [])
        return metadata.get("stack", {}).get("iam_capabilities", [])


class Template:
    class TemplateRenderingException(Exception):
        def __init__(self, template):
            super().__init__("Template could not be rendered")
            self.template = template

    def __init__(self, name: str, provider: GenericProvider, helpers: TemplateHelpers = None):
        if type(name) != str:
            raise Exception(f"Invalid template name {name}")

        self.name = name
        self.provider = provider
        self.helpers = helpers

    def render(self, vars: dict, fail_on_error: bool = False) -> str:
        raw_template = str(self.provider.template(), "utf-8")

        content = None
        env = Environment(line_statement_prefix="##", undefined=StrictUndefined)

        if self.helpers:
            self.helpers.inject(env)

        content = None
        # This will fail if rendered template can't be processed via Jinja2 (e.g. undefined variable access etc)
        try:
            content = env.from_string(source=raw_template).render(vars)

            # "@@{{ some expression }}@@" is the same as {{ some expression }}
            #
            # Helps workaround YAML formatting when editing unquoted {{ jinja expression }}
            #
            content = re.sub(r'"@@(.*)@@"', r"\g<1>", content)

            return RenderedTemplate(name=self.name, content=content)
        except (BaseException, ValueError) as ex:
            template = FailedTemplate(name=self.name, source=(content or raw_template), location=str(self.provider), error=ex)
            if fail_on_error:
                raise self.TemplateRenderingException(template)
            return template


class TemplateWithConfig(Template):
    def __init__(self, provider: GenericProvider, config: Config):
        self.vars = config.vars

        helpers = TemplateHelpers(provider=provider, bucket=CfnBucket(config=config.aws), custom_helpers=config.helpers, config=config)

        # Ugly hack alert. Injecting template commit information to vars.deploy() object here
        try:
            head = provider.head()
            if head:
                if "deploy" in config.vars:
                    deploy = config.vars["deploy"]
                    deploy.template_sha = str(head.hexsha)
                    deploy.template_ref = str(provider.git_ref)
                else:
                    log.info("Skipping setting template git info, no deploy object in config.vars")
            else:
                log.info("No head() for template repo")
        except Exception as ex:
            log.warning("Unable to add template git info", exc_info=ex)

        super().__init__(name=config.template_source.name, provider=provider, helpers=helpers)

    def render(self, fail_on_error: bool = False) -> str:
        return super().render(self.vars, fail_on_error=fail_on_error)
