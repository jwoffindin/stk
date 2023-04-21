from __future__ import annotations
from dataclasses import dataclass

from .provider import provider


@dataclass
class TemplateSource:
    """
    Template source defines the origin/source of templates (and associated files).

    We support:
    * Local filesystem
    * Local git repository
    * Remote git repository
    """

    name: str
    """name of root template (without .yaml/.yml extension)"""

    root: str = None
    """path to file - either local, or relative to git root if using repo"""

    version: str = None
    """if set, template is stored in git repository (either local or remote)"""

    repo: str = None
    """required git url if version specified. Ignored if :version: is blank/None"""

    def provider(self):
        return provider(self)
