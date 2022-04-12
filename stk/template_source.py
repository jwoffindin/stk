from __future__ import annotations
from dataclasses import dataclass

from .provider import provider

@dataclass
class TemplateSource:
    name: str
    version: str
    repo: str

    def provider(self):
        return provider(self)
