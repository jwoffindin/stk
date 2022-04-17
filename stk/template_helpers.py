from __future__ import annotations
from dataclasses import dataclass

import hashlib
from pyclbr import Function
import re
import time

from importlib import util as importutil
from io import BytesIO
from typing import Tuple
from jinja2 import Environment
from os import path
from pathlib import Path
from stat import S_IFLNK
from zipfile import ZipFile, ZipInfo, ZIP_BZIP2

from .cfn_bucket import CfnBucket, Uploadable
from .ignore_file import parse_ignore_list


@dataclass
class ZipContent(Uploadable):
    name: str
    content: bytes
    md5sum: str

    def body(self) -> bytes:
        return self.content

    def key(self) -> str:
        return "/".join([self.name, self.md5sum + ".zip"])


class TemplateHelpers:
    def __init__(self, provider, bucket: CfnBucket, custom_helpers: list):
        self.provider = provider
        self.bucket = bucket
        self.custom_helpers = {}

        for name in custom_helpers:
            self.custom_helpers[name] = self._load_custom_helper(name)

    def inject(self, env: Environment):
        """
        Inject helpers into a Jinja2 environment. We have a set of core (standard) helpers that
        should be useful for most projects.

        Template projects can define custom helpers for domain-specific logic.
        """
        g = env.globals

        # Core helpers
        g["resourcify"] = self.resourcify
        g["lambda_uri"] = self.lambda_uri

        # Custom helpers (defined in templates/helpers and specified in config via 'helpers' stanza)
        for name, func in self.custom_helpers.items():
            # Do this via func to avoid late binding problems
            # https://stackoverflow.com/questions/3431676/creating-functions-in-a-loop
            g[name] = self._make_helper_wrapper(func)

    def _make_helper_wrapper(self, func):
        return lambda *args, **kwargs: func(self, *args, **kwargs)

    def resourcify(self, name) -> str:
        """
        Given a string with non-alphanumeric characters, maps to a string that can be used as an AWS Resource name.
        """
        return re.sub(r"(\A|\W)+(\w)", lambda m: m.group(2).upper(), str(name))

    IGNORE_FILE = ".package-ignore"

    def lambda_uri(self, name: str) -> str:
        lambda_path = path.join("functions", name)
        return self.bucket.upload(self.zip_tree(dir=lambda_path, ignore=self.ignore_list(lambda_path))).as_http()

    def ignore_list(self, p: str) -> Function:
        provider = self.provider

        # Ignore files in $TEMPLATE_ROOT/$type/$name or $TEMPLATE_ROOT/$type
        dir = Path(p)
        ignore_files = [str(dir.parent / self.IGNORE_FILE), str(dir / self.IGNORE_FILE)]

        # Make a merged ignore list (and also add the .package-ignore to the list)
        ignore_content = "\n".join([self.IGNORE_FILE] + [str(provider.content(p), "utf-8") for p in ignore_files if provider.is_file(p)])

        # Parse final list
        return parse_ignore_list(ignore_content)

    def zip_tree(self, dir: str, ignore=None, prefix="") -> ZipContent:
        """
        Compress directory tree (root), setting prefix for files inside zip
        """
        checksums = {}

        zip_content = BytesIO()
        with ZipFile(zip_content, mode="w", compression=ZIP_BZIP2) as zip:
            for file_path, type, file_content in self.provider.find(dir, ignore):
                file_path = path.join(prefix, file_path)

                # Add file to zip
                info = ZipInfo(filename=file_path, date_time=time.localtime(time.time())[:6])
                info.file_size = len(file_content)

                # Set file perm ugo=rx, preserve symlinks - 0xa000 (0x120000) bit
                info.external_attr = (0o120755 if type == "symlink" else 0o555) << 16

                zip.writestr(info, data=file_content, compress_type=ZIP_BZIP2)

                # Record md5 checksum
                checksums[path.join(dir, file_path)] = hashlib.md5(str(file_content).encode("utf-8")).hexdigest()

        # final (composite) checksum is based on filenames and content md5s
        md5sum = hashlib.md5(str(sorted(checksums)).encode("utf-8")).hexdigest()

        return ZipContent(dir, zip_content.getvalue(), md5sum)

    def _load_custom_helper(self, name: str):
        """
        TBH I don't really understand this, stolen from stack overflow 😱
        """
        mod_name = f"stk.template_helpers.config.{name}"

        mod_file = str(Path("helpers", name).with_suffix(".py"))
        mod_path = self.provider.cached_path(mod_file)

        spec = importutil.spec_from_file_location(mod_name, mod_path)

        if spec is None:
            raise ImportError(f"Could not load spec for module '{mod_name}' at: {mod_file} ({mod_path})")

        module = importutil.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except FileNotFoundError as e:
            raise ImportError(f"{e.strerror}: {mod_path}") from e

        helper_func = getattr(module, "helper")

        return helper_func
