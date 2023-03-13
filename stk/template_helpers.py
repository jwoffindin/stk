from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import re
import shutil
import tempfile
import time

from dataclasses import dataclass
from importlib import util as importutil
from os import path
from pathlib import Path
from typing import IO
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

import jinja2

from jinja2 import Environment

from . import log
from .human_bytes import HumanBytes
from .cfn_bucket import CfnBucket, Uploadable
from .ignore_file import parse_ignore_list
from .multipart_encoder import multipart_encode
from .config import Config
from .provider import GenericProvider


@dataclass
class ZipContent(Uploadable):
    name: str
    content: IO
    md5sum: str

    def body(self) -> IO:
        return self.content

    def key(self) -> str:
        return "/".join([self.name, self.md5sum + ".zip"])


@contextlib.contextmanager
def in_tmp_directory():
    temp_dir = tempfile.mkdtemp()
    try:
        saved_dir = os.getcwd()
        os.chdir(temp_dir)
        yield
    finally:
        os.chdir(saved_dir)
        shutil.rmtree(temp_dir)


class TemplateHelpers:
    def __init__(self, provider: GenericProvider, bucket: CfnBucket, custom_helpers: list, config: Config):
        self.provider = provider
        self.bucket = bucket
        self.config = config
        self.custom_helpers = {}

        # These are "short-cuts" for use by custom helpers
        self.aws = config.aws

        with in_tmp_directory():
            os.mkdir("helpers")
            for name in custom_helpers:
                self.custom_helpers[name] = self._load_custom_helper(name)

    def inject_helpers(self, env: Environment):
        """
        Inject helpers into a Jinja2 environment. We have a set of core (standard) helpers that
        should be useful for most projects.

        Template projects can define custom helpers for domain-specific logic.
        """
        log.debug("injecting helpers into jinja environment")
        funcs = env.globals

        # Core helpers
        funcs["resourcify"] = self.resourcify
        funcs["lambda_uri"] = self.lambda_uri
        funcs["lambda_code"] = self.lambda_code
        funcs["user_data"] = self.user_data
        funcs["include_file"] = self.include_file
        funcs["upload_zip"] = self.upload_zip
        funcs["tags"] = self.tags
        funcs["resource_cidr"] = self.resource_cidr
        funcs["b64encode"] = self.b64encode

        # Core filters
        filters = env.filters
        filters['b64encode'] = self.b64encode

        # Custom helpers (defined in templates/helpers and specified in config via 'helpers' stanza)
        for name, func in self.custom_helpers.items():
            # Do this via func to avoid late binding problems
            # https://stackoverflow.com/questions/3431676/creating-functions-in-a-loop
            funcs[name] = self._make_helper_wrapper(func)

    def _make_helper_wrapper(self, func):
        return lambda *args, **kwargs: func(self, *args, **kwargs)

    def b64encode(self, s: str) -> str:
        """Base64 encode a string, used both as a filter and a function"""
        return base64.b64encode(s.encode('utf-8')).decode('utf-8')

    def resourcify(self, name) -> str:
        """
        Given a string with non-alphanumeric characters, maps to a string that can be used as an AWS Resource name.
        """
        return re.sub(r"(\A|\W)+(\w)", lambda m: m.group(2).upper(), re.sub(r"(_|-)+", " ", str(name))).replace(" ", "")

    IGNORE_FILE = ".package-ignore"

    def lambda_uri(self, name: str, prefix: str="") -> str:
        """Upload lambda to S3 and return an https URI to the code"""
        lambda_path = path.join("functions", name)

        zipped = self.zip_tree(dir=lambda_path, ignore=self.ignore_list(lambda_path), prefix=prefix)
        return self.bucket.upload(zipped).as_s3()

    def lambda_code(self, name: str, prefix: str="") -> dict:
        """Upload lambda to S3 and return a {S3Bucket, S3Key} pair to the result"""
        lambda_path = path.join("functions", name)

        zipped = self.zip_tree(dir=lambda_path, ignore=self.ignore_list(lambda_path), prefix=prefix)
        uploaded = self.bucket.upload(zipped)

        return {"S3Bucket": uploaded.bucket.bucket_name, "S3Key": uploaded.key}

    def ignore_list(self, p: str):
        provider = self.provider

        # Ignore files in $TEMPLATE_ROOT/$type/$name or $TEMPLATE_ROOT/$type
        dir = Path(p)
        ignore_files = [str(dir.parent / self.IGNORE_FILE), str(dir / self.IGNORE_FILE)]

        # Make a merged ignore list (and also add the .package-ignore to the list)
        ignore_content = "\n".join([self.IGNORE_FILE] + [str(provider.content(p), "utf-8") for p in ignore_files if provider.is_file(p)])

        # Parse final list
        return parse_ignore_list(ignore_content)

    def user_data(self, name: str, **extra_vars) -> str:
        """
        Given a named user_data/<name> directory, generates UserData content
        """
        dir = path.join("user_data", name.lower())
        log.debug("adding user_data from %s", dir)

        if not self.provider.is_tree(dir):
            raise (Exception(f"{dir} is not a directory"))

        # Jinja2 evaluation requires any referenced variables be defined
        # to avoid hard-to-detect failures.
        log.debug("setting up jinja environment")
        env = jinja2.Environment(line_statement_prefix="##", undefined=jinja2.StrictUndefined)
        self.inject_helpers(env)

        # context for template evaluation is 'config.vars' plus any additional
        # parameters passed. E.g.
        #
        #     user_data(name='foo', param1='bar', param2='buzz')
        #
        template_context = {**self.config.vars, **extra_vars}

        # Build dict of { name => content } that we can encode
        parts = {}
        for part_name, content_type, content in self.provider.find(dir):
            log.debug("processing part %s type=%s", part_name, content_type)
            if content_type != "file":
                raise Exception("user_data(): %s is not a regular file" % part_name)

            # Userdata files are actually Jinja2 templates in disguise
            template = env.from_string(source=str(content, "utf-8"))
            log.debug("rendering template for part %s", part_name)
            parts[part_name] = template.render(template_context)

        log.debug("performing multipart encode")
        encoded = multipart_encode(sorted(parts.items()))

        # Map encoded multi-line string to a JSON array.
        #
        # To allow resource references within user data, json fragments
        # can be embedded within << >> delimeters.
        #
        # for example: "hello <<{"Ref": "bar"}>> there <<{}>>" will be mapped
        # to a json array ["hello ", {"Ref": "bar"}, " there ", {}]
        #
        log.debug("processing break-outs")
        lines = []
        for line in encoded.splitlines(keepends=True):
            parts = re.split("<<(.+?)>>(?!>)", line)
            for i, match in enumerate(parts):
                if i % 2:
                    log.debug("processing json block %s", match)
                    lines.append(json.loads(match))
                else:
                    lines.append(match)

        # Rendering user data as correctly indented content is hard, so
        # don't even bother - just dump out single-line JSON !
        log.debug("user_data complete")
        return json.dumps({"Fn::Base64": {"Fn::Join": ["", lines]}})

    def tags(self, extra_attributes={}, **tags):
        final_tags = Config.Tags({**self.config.tags, **tags}, {})
        return final_tags.to_list(extra_attributes=extra_attributes)

    def resource_cidr(self, resource_id):
        """
        Find CIDR for subnet or VPC (AWS resources with a CIDR associated), otherwise
        just returns resource_id.
        """
        ec2 = self.aws.resource("ec2")
        if resource_id.startswith("subnet-"):
            return ec2.Subnet(resource_id).cidr_block
        elif resource_id.startswith("vpc-"):
            return ec2.Vpc(resource_id).cidr_block
        else:
            # Maybe passed in a CIDR already
            return resource_id

    def include_file(self, include_file_name, padding=8, prefix="\n", **extra_vars) -> str:
        env = Environment(line_statement_prefix="##", undefined=jinja2.StrictUndefined)

        self.inject_helpers(env)

        content = self.provider.content(path.join("files", include_file_name))
        template = env.from_string(source=str(content, "utf-8"))

        # context for evalation is 'config.vars' plus any additional parameters passed via
        # :extra_vars:
        result = template.render({**self.config.vars, **extra_vars})

        indended = "\n".join(map(lambda line: " " * padding + line, result.splitlines())) + "\n"

        return prefix + indended

    def upload_zip(self, dir: str, prefix: str = "", returns: str = "key") -> str:
        zipped = self.zip_tree(dir=dir, prefix=prefix)

        res = self.bucket.upload(zipped)
        if returns == "key":
            return res.key
        elif returns == "s3-uri":
            return res.as_s3()
        elif returns == "http-uri":
            return res.as_http()
        else:
            raise Exception(f"Unknown 'returns' value {returns} - expect one of (key, s3-uri, http-uri)")

    def zip_tree(self, dir: str, ignore=None, prefix="") -> ZipContent:
        """
        Compress directory tree (root), setting prefix for files inside zip
        """
        checksums = {}

        tmp_file = tempfile.TemporaryFile()
        with ZipFile(tmp_file, mode="w", compression=ZIP_DEFLATED) as zip:
            log.info(f"Adding files from {dir}")
            count, size = 0, 0
            for file_path, type, file_content in self.provider.find(dir, ignore):
                file_size = len(file_content)
                log.debug(" adding file %s (size=%s, type=%s)", HumanBytes.format(file_size), file_path, type)
                file_path = path.join(prefix, file_path)

                # Add file to zip
                info = ZipInfo(filename=file_path, date_time=time.localtime(time.time())[:6])
                info.file_size = file_size

                # Set file perm ugo=rx, preserve symlinks - 0xa000 (0x120000) bit
                info.external_attr = (0o120755 if type == "symlink" else 0o555) << 16

                zip.writestr(info, data=file_content, compress_type=ZIP_DEFLATED)

                # Record md5 checksum
                checksums[path.join(dir, file_path)] = hashlib.md5(str(file_content).encode("utf-8")).hexdigest()

                count += 1
                size += info.file_size

            log.info("Added %d files, total %s", count, HumanBytes.format(size))

        # final (composite) checksum is based on filenames and content md5s. They are sorted so checksum doesn't
        # vary if files are discovered in different orders.
        sorted_checksums = sorted(checksums.items())
        md5sum = hashlib.md5(str(sorted_checksums).encode("utf-8")).hexdigest()

        tmp_file.seek(0)  # required?

        return ZipContent(dir, tmp_file, md5sum)

    def _load_custom_helper(self, name: str):
        """
        TBH I don't really understand this, stolen from stack overflow 😱
        """
        mod_name = f"stk.template_helpers.config.{name}"

        mod_file = str(Path("helpers", name).with_suffix(".py"))

        log.debug("retrieving helper %s from provider", mod_file)
        content = self.provider.content(mod_file)

        log.debug("writing helper code to %s", mod_file)
        open(mod_file, "wb").write(content)

        spec = importutil.spec_from_file_location(mod_name, mod_file)

        if spec is None:
            raise ImportError(f"Could not load spec for module '{mod_name}' at: {mod_file}")

        module = importutil.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except FileNotFoundError as e:
            raise ImportError(f"{e.strerror}: {mod_file}") from e

        helper_func = getattr(module, "helper")

        return helper_func
