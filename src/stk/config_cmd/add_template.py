
import difflib
import os
import pathlib
import sys
from typing import Any, Dict
from dataclasses import dataclass

import yaml
from rich.prompt import Prompt

from .. import clog, console
from ..provider import GitProvider


@dataclass
class RemoteFile:
    """
    Tuple of <content,provider>
    """
    content: str
    provider: GitProvider

    def template_config(self) -> dict:
        """
        returns config for template location that can be put into a config file; this exists
        due to inconsistent naming between internal fields and user config. Needs to be fixed.
        """
        return { "root": self.provider.root or "/", "version": self.provider.git_ref, "repo": self.provider.git_url }

class AddTemplateCmd:
    """
    Fetch information about template from remote repository and add configuration
    for it to this project.

    * Lots of assumptions, should work for simple cases
    """

    def __init__(self, repo_url: str, config_dir: str = ".") -> None:
        #
        self.config_dir = config_dir

        self.providers = []

        default = self._common("template")
        self.providers.append(
            GitProvider(
                    "upstream",
                    git_url=default["repo"],
                    root=default["root"],
                    git_ref=default["version"]
            )
        )

        if repo_url:
            self.providers.insert(
                0,
                GitProvider(
                    name="templates",
                    git_url=repo_url,
                    root="/",
                    git_ref="main"
                )
            )

        provider_urls = [provider.git_url for provider in self.providers]
        clog(f"Using { ', '.join(provider_urls) } for remote template source")

    def add(self, name: str, follow_refs: bool = True, inline: bool = False, local_template_dir: str = "templates") -> None:
        """
        Generate local configuration for remote template

        follow_refs: if true, will attempt to add referenced stacks (if they don't exist)
        """
        template_filename = name + ".yaml"

        # Load remote template
        try:
            template = self.remote_content(template_filename)
        except FileNotFoundError:
            # Refs use underscore (since yaml doesn't like hyphens in keys), but have been using hyphens
            # in stack names. Bit of a hack here :-/
            kebab_name = name.replace('_', '-')
            if kebab_name != name:
                clog(f"{template_filename}.yaml not found in remote repository, trying kebab-case version")
                self.add(kebab_name, follow_refs=follow_refs, inline=inline, local_template_dir=local_template_dir)
                return
            clog(f"{template_filename} not found in remote repository. Aborting")
            exit(-1)

        # Load meta-data associated with remote template
        #  file in template repository with _ prefix
        metadata_filename = "_" + template_filename

        metadata: Dict[str, Any] = {"config": {}}
        try:
            # Try to find metadata - only in the same provider, don't search self.providers
            template_metadata = self.remote_content(metadata_filename, provider=template.provider)
            metadata = dict(yaml.safe_load(template_metadata.content))
            # generate configuration file first (to avoid potential looks with auto-add)
            if metadata["config"] is None:
                metadata["config"] = {}
        except FileNotFoundError:
            clog(f"{metadata_filename} does not exist in remote repository - guessing defaults")

        # Build config object for this stack
        config = {
            "includes": ["common"],
            "environments": {x: None for x in self.core_environments()},
            **metadata.get("config"),  # type: ignore
        }

        if inline:
            # Make a local copy of the template under `local_template_dir`, and config file
            # will reference this local copy. Not ideal in the long term, but easy way to
            # get started
            clog(f"Writing local template to {os.path.join(local_template_dir, template_filename)}")
            config["template"] = { "root": local_template_dir, "version": None, "repo": None }
            self.write_local_file(local_template_dir, template_filename, content=template.content)
        else:
            # If template comes from repo that is not the default, override it in the config
            if template.template_config() != self._common()["template"]:
                config["template"] = template.template_config()

        # Wrote configuration file
        clog(f"Writing config file {name}.yml")
        content = [f"# Starting configuration for deploying stack {name}\n"]
        if "description" in metadata and metadata["description"]:
            description = ["# " + line for line in metadata["description"].splitlines(keepends=True)]
            content += description  # type: ignore

        content += [
            yaml.safe_dump(config, default_flow_style=False, explicit_start=True, sort_keys=False)
        ]

        self.write_local_file(name + ".yml", content="".join(content))

        # try to resolve referenced stacks. E.g. if "ec2" stack depends on "vpc", then we
        # automatically do an "add" for "vpc" stack.
        if follow_refs and "refs" in metadata["config"]:
            for ref in metadata["config"]["refs"].keys():
                if self.is_local_file(ref + ".yml") or self.is_local_file(ref + ".yaml"):
                    clog(f"skipping {ref} - config exists already")
                else:
                    self.add(ref, local_template_dir=local_template_dir)


    def is_local_file(self, *p) -> bool:
        """
        Returns true if path exists in config directory
        """
        local_file = os.path.join(self.config_dir, *p)
        return os.path.isfile(local_file)

    def remote_content(self, *p, provider=None) -> RemoteFile:
        """
        Returns content of remote file
        """
        if provider:
            if provider.is_file(*p):
                content = str(provider.content(*p), encoding="utf-8")
                return RemoteFile(content, provider)
        else:
            for provider in self.providers:
                if provider.is_file(*p):
                    content = str(provider.content(*p), encoding="utf-8")
                    return RemoteFile(content, provider)

        raise FileNotFoundError(f"unable to find {os.path.join(*p)} in any remotes")

    def local_content(self, *p) -> str:
        """
        Create local file (only if it doesn't exist)
        """
        local_file = os.path.join(self.config_dir, *p)
        with open(local_file, "r", encoding="utf-8") as fh:
            return fh.read()

    def write_local_file(self, *p, content: str):
        """
        Create local file (only if it doesn't exist)
        """
        local_file = os.path.join(self.config_dir, *p)
        pathlib.Path(local_file).parents[0].mkdir(parents=True, exist_ok=True)
        try:
            with open(local_file, "x", encoding="utf-8") as out:
                out.write(content)
            return
        except FileExistsError:
            with open(local_file, "r", encoding="utf-8") as inp:
                original_content = inp.read()
            if original_content == content:
                clog(f"...skipping {local_file}, file already exists and is identical")
                return

        # Print diff of current/proposed and prompt user if they want to overwrite
        diff = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile='current',
            tofile='proposed',
            lineterm="\n"
        )
        sys.stdout.writelines(diff)

        # Confirm with user whether they want to overwrite, skip, or abort
        answer = Prompt.ask(f"Overwrite {local_file} ?", console=console, choices=["y", "n", "q"], default="n")
        if answer == "y":
            with open(local_file, "w", encoding="utf-8") as out:
                out.write(content)
            return
        elif answer == "n":
            clog(f"skipping {local_file}")
        else:
            clog("Aborting")
            sys.exit(-1)

    def core_environments(self):
        """
        Return configured environments. By convention, these should be
        defined in includes/common.yaml
        """
        return self._common()["core"]["environments"]

    def _common(self, *keys):
        config = yaml.safe_load(self.local_content("includes/common.yml"))
        for key in keys:
            config = config.get(key, {})
        return config


if __name__ == "__main__":
    AddTemplateCmd("git@github.com:jwoffindin/stk-templates.git",
                   config_dir="./tmp").add("vpc")
