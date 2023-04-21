import os
import random
import sys

from dataclasses import dataclass
from typing import List

import boto3
import inquirer
import yaml
import botocore

from git.repo import Repo

from .. import clog


class InitCmd:
    """
    Interactive process taking the user through the setup of a new
    config project.

    Creates a new directory, writes configuration files, creates new git repo
    and adds files.
    """

    def __init__(self, directory) -> None:
        self.config = {}
        self.directory = directory
        self.repo: Repo

    def new(self, **kwargs):
        """
        Entrypoint
        """
        self._build_config(**kwargs)

        self._create_config_dir()
        self._git_init()
        self._write_config_files()
        self._commit_config_files()

    def _build_config(self, repo: str, profile: str = "", region: str = "", bucket: str = "", environments: List = []):
        """
        Sets self.config to be hash of files and their content that are to be written to
        new config project
        """
        if os.path.exists(self.directory):
            print(f"{self.directory} already exists")
            sys.exit(-2)

        if not environments:
            environments = self._gather_environments()

        aws = self._gather_aws_settings(
            profile=profile,
            region=region,
            bucket_name=bucket
        )

        common_config = {
            **aws,
            "environments": {x: None for x in environments},
            "core": {"environments": environments},
        }

        common_config["template"] = {
            "root": "/",
            "version": "main",
            "repo": repo,
        }

        # This is really only useful for template development
        # Probably put this in a toggle, or just document it
        # if "dev" in environments:
        #     envs = common_config["environments"]
        #     if envs["dev"] is None:
        #         envs["dev"] = {}
        #
        #     envs["dev"]["template"] = {
        #         "version": None,
        #         "repo": None,
        #         "root": '{{ environ["TEMPLATE_PATH"] }}',
        #     }

        yaml.SafeDumper.add_representer(
            type(None),
            lambda x, value: x.represent_scalar("tag:yaml.org,2002:null", "")
        )

        self.config = {
            "includes/common.yml": yaml.safe_dump(
                common_config,
                default_flow_style=False,
                explicit_start=True, sort_keys=False
            ),
            ".gitignore": "*.log\n.template-cache\n"
        }

    def _create_config_dir(self):
        clog(f"creating new config project {self.directory}")
        os.mkdir(self.directory)

    def _git_init(self):
        clog("initializing new git repository")
        self.repo = Repo.init(self.directory)

    def _write_config_files(self):
        clog("writing configuration files")
        for filename, content in self.config.items():
            full_path = os.path.join(self.directory, filename)
            dir_name = os.path.dirname(full_path)
            if not os.path.exists(dir_name):
                os.mkdir(dir_name)

            with open(full_path, "x", encoding="utf-8") as fh:
                fh.write(content)

    def _commit_config_files(self):
        clog("committing new files")
        self.repo.index.add(list(self.config.keys()))
        self.repo.index.commit(
            "Initial configuration added by cfn config init"
        )

    @dataclass
    class GatherAwsSettings:
        """
        Build settings for AWS - optionally creating an S3 bucket if required
        """
        region: str
        profile: str
        bucket_name: str

        def gather(self):
            """
            Handle process of collecting AWS settings - profile, region and CFN bucket
            """
            questions = []

            self._gather_profile(questions)
            self._gather_region(questions)

            aws_settings = {
                "profile": self.profile,
                "region": self.region,
            }

            answers = inquirer.prompt(questions)
            if answers:
              aws_settings = {**aws_settings, **answers}

            self._gather_bucket(**aws_settings)

            aws_settings["cfn_bucket"] = self.bucket_name

            return aws_settings

        def _gather_profile(self, questions: List):
            session = boto3.session.Session()
            if not self.profile:
                profiles = session.available_profiles
                if not profiles:
                    print(
                        "Your aws configuration does not set any profiles. Run `aws configure`")
                    sys.exit(-1)

                # Don't bother if user only has one profile configured
                if self.profile is None:
                    if len(profiles) == 1:
                        self.profile = profiles[0]

                if not self.profile:
                    questions.append(
                        inquirer.List(
                            "profile",
                            message="Select AWS Profile to use",
                            choices=profiles,
                        )
                    )

        def _gather_region(self, questions: List):
            session = boto3.session.Session()
            if self.region is None:
                regions = sorted(session.get_available_regions("ec2"))
                questions.append(
                    inquirer.List(
                        "region",
                        message="What AWS region to you want to deploy to?",
                        choices=regions,
                        default="us-west-2"
                    )
                )

        def _gather_bucket(self, region: str, profile: str):
            # Now that we have profile/region - we can figure out what bucket to use
            if not self.bucket_name:
                session = boto3.session.Session(
                    profile_name=profile, region_name=region)

                try:
                    s3_client = session.client("s3")
                    create_option = "NONE - create a new bucket"

                    buckets = [create_option]
                    for bucket_name in s3_client.list_buckets()["Buckets"]:
                        name = bucket_name['Name']
                        location = s3_client.get_bucket_location(Bucket=name)
                        if (region == 'us-east-1' and location['LocationConstraint'] == None) or location['LocationConstraint'] == region:
                            buckets.append(name)

                    bucket_answer = inquirer.prompt([
                        inquirer.List(
                            "bucket", message="Select bucket to use for cloudformation templates", choices=buckets)
                    ])

                    if not bucket_answer:
                        print("aborting")
                        sys.exit(-1)

                    if bucket_answer["bucket"] != create_option:
                        self.bucket_name = bucket_answer['bucket']
                        return

                    self.bucket_name = f"cf-templates-{region}-{'%015x' % random.getrandbits(60)}"

                    clog(f"creating s3 bucket {self.bucket_name}")

                    if region == 'us-east-1':
                      s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                      s3_client.create_bucket(Bucket=self.bucket_name, CreateBucketConfiguration={'LocationConstraint': region})

                    s3_client.put_public_access_block(
                        Bucket=self.bucket_name,
                        PublicAccessBlockConfiguration={
                            'BlockPublicAcls': True,
                            'IgnorePublicAcls': True,
                            'BlockPublicPolicy': True,
                            'RestrictPublicBuckets': True
                        },
                    )

                except botocore.exceptions.NoCredentialsError as ex:
                    print(
                        f"Unable to retrieve list of buckets using {profile}: {ex}")
                    sys.exit(-1)

    def _gather_aws_settings(self, **kwargs) -> dict:
        """
        Gather information about AWS deployment
        """
        settings = self.GatherAwsSettings(**kwargs).gather()

        return {"aws": settings}

    def _gather_environments(self) -> List:
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

        if answers:
            envs = answers["environments"]
            if envs:
                return envs

        return ["dev, test", "prod"]


if __name__ == "__main__":
    InitCmd("tmp").new()
