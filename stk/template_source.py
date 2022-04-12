from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import posix

@dataclass
class TemplateSource:
    name: str
    version: str
    repo: str

    def provider(self):
        if self.repo.startswith('/') or self.repo.startswith('.'):
            return FilesystemTemplateSource(path=self.repo, name=self.name)
        raise Exception("Unsupported template source")

@dataclass
class FilesystemTemplateSource():
    name: str
    path: str

    def __post_init__(self):
        if not Path(self.path).is_dir:
            raise Exception(f'{self.path} does not appear to be a directory')

    def template(self):
        tpl_path = Path(self.path, self.name)
        if not tpl_path.suffix:
            tpl_path = tpl_path.with_suffix('.yaml')
        return open(tpl_path, "rb").read()

    def __str__(self) -> str:
        return self.name
