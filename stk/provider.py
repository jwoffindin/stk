from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path



class GenericProvider():
    pass
@dataclass
class FilesystemProvider(GenericProvider):
    name: str
    path: str

    def __post_init__(self):
        if not Path(self.path).is_dir:
            raise Exception(f'{self.path} does not appear to be a directory')
        print(f"**** provider = {self}")

    def template(self):
        tpl_path = Path(self.path, self.name)
        if not tpl_path.suffix:
            tpl_path = tpl_path.with_suffix('.yaml')
        return open(tpl_path, "rb").read()

    # def content(self, *path) -> str:
    #     tpl_path = Path(self.path, *path)
    #     return open(tpl_path, "rb").read()

    def cached_path(self, *path) -> str:
        return Path(self.path, *path)

    def __str__(self) -> str:
        return self.name

def provider(source):
    repo = source.repo
    if repo.startswith('/') or repo.startswith('.'):
        return FilesystemProvider(path=repo, name=source.name)
    raise Exception("Unsupported template source")
