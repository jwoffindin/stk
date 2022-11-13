import os
import sys
import yaml

from .. import clog
from ..provider import GitProvider


class AddTemplateCmd:
    """
    Fetch information about template from remote repository and add configuration
    for it to this project.

    * Lots of assumptions, should work for simple cases
    """

    def __init__(self, repo_url: str, config_dir: str = ".") -> None:
        #
        self.config_dir = config_dir

        # If no repo is provided, use the default configuration from includes/common.yml
        if not repo_url:
            default = self._common("template")
            if default:
                self.repo_url = default["repo"]
                self.provider = GitProvider(
                    "templates",
                    git_url=default["repo"],
                    root=default["root"],
                    git_ref=default["version"]
                )
            else:
                print(
                    """unable to determine default template repository.

                    Please pass --repo with git url of template repository
                    """
                )
                sys.exit(-1)
        else:
            self.repo_url = repo_url
            self.provider = GitProvider(
                name="templates",
                git_url=repo_url,
                root="/",
                git_ref="main"
            )

        clog(f"Using {self.provider.git_url} for remote template source")

    def add(self, name: str, follow_refs: bool = True) -> None:
        """
        Generate local configuration for remote template

        follow_refs: if true, will attempt to add referenced stacks (if they don't exist)
        """
        template_path = name + ".yaml"
        if not self.is_remote_file(template_path):
            clog(
                f"{template_path} is not a file, or does not exist in remote repository")
            sys.exit(-1)

        # Info file in template repository has leaving prefix
        info_path = "_" + template_path
        if not self.is_remote_file(info_path):
            clog(f"{info_path} does not exist in remote repository - guessing defaults")
            metadata = {"config": None}
        else:
            metadata = yaml.safe_load(self.remote_content(info_path))

        if metadata["config"] is None:
            metadata["config"] = {}

        # generate configuration file first (to avoid potential looks with auto-add)

        config = {
            "includes": ["common"],
            "environments": {x: None for x in self.core_environments()},
            **metadata.get("config"),
        }

        template = {"root": "/", "version": "main", "repo": self.repo_url}
        if template != self._common()["template"]:
            config["template"] = template

        clog(f"Writing config file {name}.yml")
        content = [f"# Starting configuration for deploying stack {name}\n"]
        if "description" in metadata and metadata["description"]:
            content += ["# " +
                        line for line in metadata["description"].splitlines(keepends=True)]
        content += [yaml.safe_dump(config, default_flow_style=False,
                                   explicit_start=True, sort_keys=False)]

        self.write_local_file(name + ".yml", content="".join(content))

        # try to resolve referenced stacks. E.g. if "ec2" stack depends on "vpc", then we
        # automatically do an "add" for "vpc" stack.
        if follow_refs and "refs" in metadata["config"]:
            for ref in metadata["refs"].keys():
                if self.is_local_file(ref + ".yml") or self.is_local_file(ref + ".yaml"):
                    clog(f"skipping {ref} - config exists already")
                    continue

    def is_remote_file(self, *p) -> bool:
        """
        Returns true if path exists in remote repository
        """
        return self.provider.is_file(*p)

    def is_local_file(self, *p) -> bool:
        """
        Returns true if path exists in config directory
        """
        local_file = os.path.join(self.config_dir, *p)
        return os.path.isfile(local_file)

    def remote_content(self, *p) -> bool:
        """
        Returns content of remote file
        """
        return self.provider.content(*p)

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
        with open(local_file, "x", encoding="utf-8") as fh:
            fh.write(content)

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
