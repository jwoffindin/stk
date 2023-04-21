# Stolen from https://github.com/mherrmann/gitignore_parser

import os
import re

from dataclasses import dataclass
from types import FunctionType


def parse_ignore_list(ignore_content: str) -> FunctionType:
    if type(ignore_content) == bytes:
        ignore_content = str(ignore_content, "utf-8")

    rules = []
    for line in ignore_content.splitlines():
        rule = rule_from_pattern(line)
        if rule:
            rules.append(rule)

    return lambda file_path: is_ignored(file_path, rules)


def is_ignored(file_path: str, rules: FunctionType) -> bool:
    matched = False
    for rule in rules:
        if rule.match(file_path):
            matched = not rule.negation
    return matched


def rule_from_pattern(pattern):
    """
    Take a .gitignore match pattern, such as "*.py[cod]" or "**/*.bak",
    and return an IgnoreRule suitable for matching against files and
    directories. Patterns which do not match files, such as comments
    and blank lines, will return None.
    Because git allows for nested .gitignore files, a base_path value
    is required for correct behavior. The base path should be absolute.
    """

    # Store the exact pattern for our repr and string functions
    orig_pattern = pattern

    # Early returns follow
    # Discard comments and separators
    if pattern.strip() == "" or pattern[0] == "#":
        return

    # Discard anything with more than two consecutive asterisks
    if pattern.find("***") > -1:
        return

    # Strip leading bang before examining double asterisks
    if pattern[0] == "!":
        negation = True
        pattern = pattern[1:]
    else:
        negation = False

    # Discard anything with invalid double-asterisks -- they can appear
    # at the start or the end, or be surrounded by slashes
    for m in re.finditer(r"\*\*", pattern):
        start_index = m.start()
        if start_index != 0 and start_index != len(pattern) - 2 and (pattern[start_index - 1] != "/" or pattern[start_index + 2] != "/"):
            return

    # Special-casing '/', which doesn't match any files or directories
    if pattern.rstrip() == "/":
        return

    directory_only = pattern[-1] == "/"
    # A slash is a sign that we're tied to the base_path of our rule
    # set.
    anchored = "/" in pattern[:-1]
    if pattern[0] == "/":
        pattern = pattern[1:]
    if pattern[0] == "*" and len(pattern) >= 2 and pattern[1] == "*":
        pattern = pattern[2:]
        anchored = False
    if pattern[0] == "/":
        pattern = pattern[1:]
    if pattern[-1] == "/":
        pattern = pattern[:-1]
    # patterns with leading hashes are escaped with a backslash in front, unescape it
    if pattern[0] == "\\" and pattern[1] == "#":
        pattern = pattern[1:]
    # trailing spaces are ignored unless they are escaped with a backslash
    i = len(pattern) - 1
    striptrailingspaces = True
    while i > 1 and pattern[i] == " ":
        if pattern[i - 1] == "\\":
            pattern = pattern[: i - 1] + pattern[i:]
            i = i - 1
            striptrailingspaces = False
        else:
            if striptrailingspaces:
                pattern = pattern[:i]
        i = i - 1

    regex = fnmatch_pathname_to_regex(pattern, directory_only)

    if anchored:
        regex = "".join(["^", regex])

    return IgnoreRule(
        pattern=orig_pattern,
        regex=regex,
        negation=negation,
        directory_only=directory_only,
        anchored=anchored,
    )


whitespace_re = re.compile(r"(\\ )+$")


@dataclass
class IgnoreRule:
    pattern: str
    regex: re.Pattern
    negation: bool
    directory_only: bool
    anchored: bool

    def __str__(self):
        return self.pattern

    def __repr__(self):
        return "".join(["IgnoreRule('", self.pattern, "')"])

    def match(self, rel_path):
        """
        Returns true if rel_patch is matched by this rule
        """
        matched = False
        if rel_path.startswith("./"):
            rel_path = rel_path[2:]

        if re.search(self.regex, rel_path):
            matched = True

        return matched


# Frustratingly, python's fnmatch doesn't provide the FNM_PATHNAME
# option that .gitignore's behavior depends on.
def fnmatch_pathname_to_regex(pattern, directory_only: bool):
    """
    Implements fnmatch style-behavior, as though with FNM_PATHNAME flagged;
    the path separator will not match shell-style '*' and '.' wildcards.
    """
    i, n = 0, len(pattern)

    seps = [re.escape(os.sep)]
    if os.altsep is not None:
        seps.append(re.escape(os.altsep))

    seps_group = "[" + "|".join(seps) + "]"
    nonsep = r"[^{}]".format("|".join(seps))

    res = []
    while i < n:
        c = pattern[i]
        i += 1
        if c == "*":
            try:
                if pattern[i] == "*":
                    i += 1
                    res.append(".*")
                    if pattern[i] == "/":
                        i += 1
                        res.append("".join([seps_group, "?"]))
                else:
                    res.append("".join([nonsep, "*"]))
            except IndexError:
                res.append("".join([nonsep, "*"]))
        elif c == "?":
            res.append(nonsep)
        elif c == "/":
            res.append(seps_group)
        elif c == "[":
            j = i
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                res.append("\\[")
            else:
                stuff = pattern[i:j].replace("\\", "\\\\")
                i = j + 1
                if stuff[0] == "!":
                    stuff = "".join(["^", stuff[1:]])
                elif stuff[0] == "^":
                    stuff = "".join("\\" + stuff)
                res.append("[{}]".format(stuff))
        else:
            res.append(re.escape(c))

    res.insert(0, "(?ms)")

    if not directory_only:
        res.append("$")

    return "".join(res)
