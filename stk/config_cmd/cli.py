"""
  cfn config init -- create a new project
  cfn config add .... -- add config file(s) to existing project
"""
import os
from typing import List
import click

from .init import InitCmd
from .add_template import AddTemplateCmd
from stk import clog


@click.group()
def config():
    """
    Base for performing config-management commands
    """
    pass


@config.command()
@click.argument("directory")
@click.option("--repo", help="Git url for template repository", default="https://github.com/jwoffindin/stk-templates.git")
@click.option("--profile", "-p", help="New config will use this AWS profile")
@click.option("--region", "-r", help="New config will use this region")
@click.option("--bucket", "-b", help="Bucket to use ")
@click.option("--env", "-e", help="Add this environment", multiple=True)
@click.option("--templates", "-t", help="Add template(s)", multiple=True)
def init(directory: str, repo: str, profile: str, region: str, bucket: str, env: List, templates: List) -> None:
    """
    Create a new, config project, as a way to get the user started
    """
    InitCmd(directory).new(
        repo=repo,
        region=region,
        profile=profile,
        bucket=bucket,
        environments=env
    )

    for template_list in templates:
        for tpl in template_list.split(","):
            # try:
            AddTemplateCmd(repo, config_dir=directory).add(tpl)
            # except Exception as ex:
            #    clog(f"unable to add {tpl}: {ex}")


@config.command()
@click.argument("template")
@click.option("--repo", help="Path to template project")
@click.option("--inline", is_flag=True, default=False, help="Create a local copy of template")
@click.option("--template-dir", default=os.environ.get('TEMPLATE_PATH', 'templates'), help="Where --copy-template should store the template")

def add(template: str, repo: str, inline: bool, template_dir: str) -> None:
    """
    Add configuration for template from remote repository
    """
    AddTemplateCmd(repo).add(template, inline=inline, local_template_dir=template_dir)
