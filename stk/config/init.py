"""
InitCmd implements logic for 'stk config init ....', creating a new stack
config project.
"""
import re
import sys

from os import path

import boto3
import inquirer
import yaml

from stk import console


class InitCmd:
    """
    Interactive process taking the user through the setup of a new
    config project.
    """

    def __init__(self, directory) -> None:
        re.sub(r"[^\w\d-]", "-", directory)
        self.directory = directory

    def initialize(self):
        """
        Entrypoint
        """
        if path.exists(self.directory):
            print(f"{self.directory} already exists")
            exit(-2)

        aws = self.gather_aws_settings()
        environments = self.gather_environments()

        config = {
            **aws,
            "environments": {x: None for x in environments},
            "core": {"environments": environments},
        }

        config["template"] = {"root": "/", "version": "main",
                              "repo": "git@github.com:jwoffindin/stk-templates.git"}

        if "dev" in environments:
            config["dev"]["template"] = {
                "version": None,
                "repo": None,
                "root": '{{ environ["TEMPLATE_PATH"] }}',
            }

        yaml.SafeDumper.add_representer(
            type(None), lambda x, value: x.represent_scalar("tag:yaml.org,2002:null", ""))

        print(yaml.safe_dump(config, default_flow_style=False,
              explicit_start=True, sort_keys=False))

    def gather_aws_settings(self):
        """
        Gather information about AWS deployment
        """
        console.print("Select the default region for your deployments")

        session = boto3.session.Session()

        profiles = session.available_profiles
        if not profiles:
            print("Your aws configuration does not set any profiles. Run `aws configure`")
            sys.exit(-1)

        print(f"{profiles}")

        profile = None
        if len(profiles) == 1:
            profile = profiles[0]

        regions = sorted(session.get_available_regions("ec2"))

        questions = []
        if not profile:
            questions.append(
                inquirer.List(
                    "profile",
                    message="Select AWS Profile to use",
                    choices=profiles,
                )
            )

        questions.append(
            inquirer.List(
                "region",
                message="What AWS region to you want to deploy to?",
                choices=regions,
            )
        )

        answers = {"profile": profile, **inquirer.prompt(questions)}

        print(answers)

        return {"aws": answers}

    def gather_environments(self):
        """
        Allow user to specify what environment's to deploy
        """
        answers = inquirer.prompt(
            [
                inquirer.Checkbox(
                    "environments",
                    message="What environments do you want to deploy to?",
                    choices=["dev", "test", "staging", "prod"],
                    default=["dev"],
                )
            ]
        )

        return answers["environments"]


if __name__ == "__main__":
    InitCmd("tmp").initialize()
