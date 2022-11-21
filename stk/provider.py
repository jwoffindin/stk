"""
Abstracts access templates stored in either a remote git
repository, or local filesystem.
"""
from __future__ import annotations

import os
import stat
import urllib

from os import path, walk
from pathlib import Path
from dataclasses import dataclass

import giturlparse

from git.repo import Repo

from . import log


class GenericProvider:
    def template(self) -> bytes:
        tpl_path = Path(self.name)
        if not tpl_path.suffix:
            tpl_path = tpl_path.with_suffix(".yaml")
        return self.content(tpl_path)

    def content(self, _: str) -> bytes:
        pass

    def is_file(self, *_) -> bool:
        pass

    def is_dir(self, *_) -> bool:
        pass

    def find(self, dir: str, ignore: function):
        pass


@dataclass
class FilesystemProvider(GenericProvider):
    name: str
    root: str

    def __post_init__(self):
        if not Path(self.root).is_dir:
            raise Exception(f"{self.root} does not appear to be a directory")

    def head(self):
        return None

    def content(self, file_path: str) -> bytes:
        return open(path.join(self.root, file_path), "rb").read()

    def is_file(self, *p) -> bool:
        return path.isfile(path.join(self.root, *p))

    def is_tree(self, *p) -> bool:
        return path.isdir(path.join(self.root, *p))

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

    def __str__(self) -> str:
        return self.name


@dataclass
class GitProvider(GenericProvider):
    name: str
    git_url: str  # TODO rename to root
    git_ref: str
    root: str = ""

    #
    repo: Repo = None

    def __post_init__(self):
        if self.root.endswith("/"):
            self.root = self.root[:-1]

        log.debug(f"GitProvider(name={self.name}, url={self.git_url}, root={self.root})")

        if not self.git_url:
            raise Exception("template.git_url is not set")

        if self.git_url.startswith(".") or self.git_url.startswith("/"):
            # Local repository (e.g. ../templates)
            self.repo = Repo(self.git_url)
        else:
            url = urllib.parse.urlparse(self.git_url)
            log.debug(url)
            if url.scheme == "file":  # "file" in url.protocols:
                log.info("Local git repository at %s", url.path)
                self.repo = Repo(url.path)
            else:
                # Remote repository
                url = giturlparse.parse(self.git_url)
                cache_dir = self._cache_path(url)
                if path.exists(cache_dir):
                    log.info("using existing cached version %s", cache_dir)
                    self.repo = Repo(cache_dir)
                    log.info("git pull remote 'origin'")
                    self.repo.remotes["origin"].pull()
                else:
                    log.info("don't have a cached copy of %s in %s", self.git_url, cache_dir)
                    os.makedirs(cache_dir, mode=0o700, exist_ok=True)
                    log.info(f"cloning from {self.git_url} -> {cache_dir}")
                    self.repo = Repo.clone_from(self.git_url, cache_dir)

        log.info(f"getting commit {self.git_ref} from {self.repo}")
        self.commit = self.repo.commit(self.git_ref)
        log.info(f"have commit {self.commit.hexsha}")

    def content(self, *p) -> bytes:
        file_path = path.join(self.root, *p)
        try:
            log.info(f"getting content for {file_path}")
            return self.commit.tree[file_path].data_stream.read()
        except KeyError as ex:
            log.exception(f"Git object (git={self.git_url} file_path={file_path})@{self.git_ref}: does not exist", exc_info=ex)
            raise

    def head(self):
        return self.commit

    def is_file(self, *p) -> bool:
        file_path = path.join(self.root, *p)
        try:
            obj = self.commit.tree[file_path]
            if obj.type == "blob":
                return True
            return False
        except KeyError:
            return False

    def is_tree(self, *p) -> bool:
        dir_path = path.join(self.root, *p)
        try:
            obj = self.commit.tree[dir_path]
            if obj.type == "tree":
                return True
            return False
        except KeyError:
            return False

    def find(self, dir, ignore=None):
        if dir.endswith("/"):
            dir = dir[:-1]

        tree_path = path.join(self.root, dir)
        tree = self.commit.tree[tree_path]
        for item in tree.traverse():
            item_path = item.path[len(tree_path) + 1 :]
            if ignore and ignore(item_path):
                continue

            if item.type == "blob":
                if item.mode & item.link_mode == item.link_mode:
                    type = "symlink"
                else:
                    type = "file"
                yield (item_path, type, item.data_stream.read())

    def _cache_path(self, url: giturlparse.parser.Parsed) -> str:
        cache_dir = os.environ.get("TEMPLATE_CACHE", ".template-cache")
        return path.join(cache_dir, url.host, url.owner, *(url.groups), url.repo)  # type: ignore


def provider(source):
    log.info(f"provider = {source}")
    if source.version:
        root = source.root or "/"
        return GitProvider(name=source.name, git_url=source.repo, root=root, git_ref=source.version)
    else:
        return FilesystemProvider(name=source.name, root=source.root)
