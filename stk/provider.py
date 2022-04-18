from __future__ import annotations

import os
import stat

from dataclasses import dataclass
from os import path, walk
from pathlib import Path


class GenericProvider:
    pass


@dataclass
class FilesystemProvider(GenericProvider):
    name: str
    root: str  # TODO rename to root

    def __post_init__(self):
        if not Path(self.root).is_dir:
            raise Exception(f"{self.root} does not appear to be a directory")

    def template(self):
        tpl_path = Path(self.root, self.name)
        if not tpl_path.suffix:
            tpl_path = tpl_path.with_suffix(".yaml")
        return open(tpl_path, "rb").read()  # TODO change to 'r'

    def content(self, file_path):
        return open(path.join(self.root, file_path), "rb").read()

    def is_file(self, *p):
        return path.isfile(path.join(self.root, *p))

    def find(self, dir, ignore=None):
        start_dir = path.abspath(path.join(self.root, dir))

        if not path.exists(start_dir):
            raise Exception(f"{dir} does not exist in {self.root}")

        for p, _, files in walk(start_dir):
            for f in files:
                file_path = path.join(p, f)
                if ignore and ignore(file_path):
                    # print(f"Skipping {file_path} due to ignore rule")
                    continue

                # strip the directory prefix. E.g.
                #  'functions/<function-name>/foo.txt' -> foo.txt
                relative_path = file_path[len(start_dir) + 1 :]

                st = os.lstat(file_path)
                if stat.S_ISREG(st.st_mode):
                    yield (relative_path, "file", self.content(file_path))
                elif stat.S_ISLNK(st.st_mode):
                    target = os.readlink(file_path)
                    yield (relative_path, "symlink", target)
                else:
                    raise Exception("Unsupported filesystem object at " + file_path)

    def cached_path(self, *path) -> str:
        return Path(self.root, *path)

    def __str__(self) -> str:
        return self.name


def provider(source):
    repo = source.repo
    if repo.startswith("/") or repo.startswith("."):
        return FilesystemProvider(root=repo, name=source.name)
    raise Exception("Unsupported template source")
