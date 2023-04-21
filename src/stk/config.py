"""
Provides `Config` class which handles the loading of configuration and
exposing derived state.
"""
from __future__ import annotations
import json

import pathlib
import re
import os

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from sys import exc_info
from typing import Union

import git

from jinja2 import Environment, StrictUndefined
from rich.table import Table
from yaml import safe_load

from . import ConfigException, log, console, VERSION
from .config_file import ConfigFiles, ConfigFile
from .template_source import TemplateSource
from .aws_config import AwsSettings
from .stack_refs import StackRefs
from .interpolated_dict import InterpolatedDict, InterpolationError

class Config:
    """
    Represents a final, merged, configuration for a stack deployment.
    """

    @dataclass
    class CoreSettings:
        """
        Settings that change the behavior of the cfn command - not directly related
        to templates or deployments.
        """

        # Attributes
        stack_name: str
        encode_params: bool
        environments: list = None

        # DEFAULTS are pre-interpolation values so can't set them via attributes
        DEFAULTS = {
            "encode_params": False,
            "stack_name": "{{ environment }}-{{ name.replace('/', '-') }}"
        }

        # stack name
        valid_stack_name = re.compile("^[a-zA-Z0-9-]+$").match

        def __post_init__(self):
            if type(self.stack_name) != str or not self.valid_stack_name(self.stack_name):
                raise ValueError(f"Stack name {self.stack_name} is invalid. Can contain only alphanumeric characters and hyphens")

    class Vars(dict):
        MAX_INTERPOLATION_DEPTH = 10

        def __init__(self, vars: dict):
            """
            This method initializes an object with a dictionary of variables 'vars'. It expands the interpolated variables in the
            dictionary using Jinja2, and checks for any failed keys. If there are any failed keys, it creates a table of errors with
            the key name, corresponding value, and error message, and logs it to the console. It then raises an exception with a
            message indicating that an error occurred processing the 'vars' dictionary.

            This is a bit different than how to expand other Jinja-value dicts because we'll need to iterate through a few
            times until all vars have been expanded.
            """
            failed_keys = self.expand(vars)

            if failed_keys:
                errors = Table("Key", "Value", "Error")
                for k, v in failed_keys.items():
                    errors.add_row(k, str(v.value), str(v.error))
                console.log(errors)
                raise Exception(f"An error occurred processing vars: {failed_keys}")

        def expand(self, vars: dict):
            """
            Updates `self` with final interpolated values from initial dict `vars`.

            Returns dict InterpolationError for all keys that can't be expanded
            """
            env = Environment(undefined=StrictUndefined, extensions=["jinja2_strcase.StrcaseExtension"])

            interpolation_depth = 0

            errors = {}
            while interpolation_depth <= self.MAX_INTERPOLATION_DEPTH:
                interpolation_depth += 1
                unexpanded_keys = sorted(set(vars.keys()) - set(self.keys()))
                if not unexpanded_keys:
                    return None

                for key in unexpanded_keys:
                    value = vars[key]
                    try:
                        del errors[key]
                        if type(value) in [bool, dict, list, str]:
                            tpl = env.from_string(str(value))  # convert value to jinja2 template
                            result = str(tpl.render(self))
                            self[key] = safe_load(result)
                            # print(f"expanding {key}, {value}({type(value)}) -> {self[key]}({type(self[key])})")
                        else:
                            # print(f"skipping {key}, type={type(value)}")
                            self[key] = value  # Don't try and process this value as Jinja template
                        del vars[key]
                    except Exception:
                        errors[key] = InterpolationError(key, value, exc_info()[1])

            return errors

    class Tags(InterpolatedDict):
        def to_list(self, extra_attributes={}):
            ret_val = []
            for k, v in self.items():
                ret_val.append({"Key": str(k), "Value": str(v), **extra_attributes})
            return ret_val

    @dataclass
    class DeployMetadata:
        def __init__(self, config_path: str, template_source: TemplateSource):
            # Timestamp in UTC
            self.timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H:%M:%S%Z")

            # STK version
            self.deployed_with = f"stk-{VERSION}"

            root = template_source.root or ""
            name = template_source.name or ""

            if template_source.repo:
                self.template = "/".join([template_source.repo, root, name])
            else:
                self.template = "/".join([root, name])

            # Config git HEAD state - this is optional. The config project may
            # not be stored in git. Also, if config is in a subdirectory, we'd
            # too dumb to try and find git repo in a parent directory.
            try:
                config_head = git.Repo(config_path).head
                self.config_sha = str(config_head.commit.hexsha)
                self.config_ref = str(config_head.reference)
            except Exception as ex:  # pylint: disable=broad-except
                log.debug("Unable to retrieve git info for config project", exc_info=ex)
                self.config_sha = "?"
                self.config_ref = "?"

            self.template_sha = "?"
            self.template_ref = "?"

    def __init__(
        self,
        name: str,
        environment: str,
        config_path: str,
        overrides: ConfigFiles = ConfigFiles([]),
        template_path: Union[str, None] = None,
    ):
        # While we should just receive `name`, we may be be passed
        name = str(Path(name).with_suffix(""))
        self.name = name.replace("/", "-")
        self.environment = environment
        self.config_path = config_path

        try:
            cfg = ConfigFile(filename=name, config_dir=self.config_path)
            log.debug("loaded initial config file %s from %s: %s", name, self.config_path, cfg, extra={"cfg": cfg})
        except FileNotFoundError as err:
            raise Exception(f"Configuration file {name} not found in {config_path}: {err}") from err

        # Validate specified environment is defined in the top-level config file
        if environment not in cfg.environments():
            raise ConfigException(f"Environment {environment} is not a valid environment for {cfg.filename}. Only {cfg.environments()} permitted.")

        # Load top-level config file and all included configs
        includes = cfg.load_includes(overrides)

        # Most other config supports pulling stuff from AWS, so initialize this first
        aws_settings = {}
        try:
            aws_settings = InterpolatedDict(includes.fetch_dict("aws", environment), {"environ": os.environ, "environment": environment})
            self.aws = AwsSettings(**aws_settings)
            self.aws.get_account_id()  # force retrieval of account_id
        except TypeError as ex:
            raise Exception(f"Unable to parse aws settings: have {aws_settings}: {ex}") from ex

        default_vars = {
            "__config_dir": pathlib.Path(config_path),
            "account_id": self.aws.account_id,
            "aws_region": self.aws.region,
            "cfn_bucket": self.aws.cfn_bucket,
            "environ": os.environ,
            "environment": environment,
            "name": self.name,
        }

        # Core settings impact the behavior of 'stk' - e.g. stack name, valid environments
        # etc.
        self.core = self.CoreSettings(
            **InterpolatedDict(
                includes.fetch_dict("core", environment, self.CoreSettings.DEFAULTS),
                default_vars,
            )
        )

        # Ugly hack. Need to come up with something better after I've had a coffee
        default_vars["stack_name"] = self.core.stack_name

        # Stack 'refs' object references external stacks. They are intended to be resolved by 'vars'/'params' so need to be
        # loaded first
        try:
            refs = InterpolatedDict(includes.fetch_dict("refs", environment), {"environment": environment})
            self.refs = StackRefs(refs, self)
        except Exception as ex:
            raise Exception("Unable to parse stack refs (refs:). have {refs}: {ex}") from ex
        default_vars["refs"] = self.refs

        self.helpers = list(includes.fetch_set("helpers", environment))

        pre_vars = includes.fetch_dict("vars", environment, default_vars)
        self.vars = self.Vars(pre_vars)

        params = includes.fetch_dict("params", environment)
        self.params = InterpolatedDict(params, self.vars)
        if self.core.encode_params:
            self.encode_param_values(self.params)
        log.debug("setting parameters: %s", self.params)
        self.vars["params"] = self.params

        template_source = InterpolatedDict(
            includes.fetch_dict(
                "template",
                environment,
                {"name": name.replace("/", "-"), "root": None},
            ),
            self.vars,
        )

        # I'm not happy about this
        if template_source["root"] == None:
            if "repo" in template_source and template_source["repo"]:
                # git repo, we default "root" to / - i.e. relevant to git root
                template_source["root"] = "/"
            else:
                # filesystem repo, we default "root" to provided template_path (--template-path args)
                # mostly useful for tests
                template_source["root"] = template_path

        self.template_source = TemplateSource(**template_source)

        # Deploy metadata is used to track deploys back to version controlled config/templates.
        self.vars["deploy"] = self.DeployMetadata(config_path=config_path, template_source=self.template_source)

        self.tags = self.Tags(includes.fetch_dict("tags", environment), self.vars)

        # perform final linting/validation
        includes.validate(self)

    def var(self, name):
        return self.vars.get(name)

    def param(self, name):
        return self.params.get(name)

    def encode_param_values(self, params):
        """
        JSON-encode any CFN *parameters* that aren't strings. Enabled by
        setting `core.encode_params`. Useful if you want to pass structured
        data as JSON to the template (e.g. setting parameters, or secrets).
        """
        for k, value in params.items():
            if not isinstance(value, str):
                params[k] = json.dumps(value)
