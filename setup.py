#!/usr/bin/env python3

from distutils.core import setup

import re
import ast

# Can't import stk/ so "standard practice" is just to parse it as a string
version_re = re.compile(r'VERSION\s+=\s+(.*)')
with open('stk/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(version_re.search(f.read().decode('utf-8')).group(1)))

setup(
    name="stk",
    description="Opinionated CloudFormation deployments",
    license="MIT",
    author="John Woffindin <j.woffindin@gmail.com>",
    version=version,
    url="https://github.com/jwoffindin/stk",
    install_requires=["setuptools", "click", "boto3", "pyyaml", "jinja2", "rich", "cfn-flip", "gitpython", "giturlparse", "jinja2-strcase", "inquirer"],
    entry_points={
        "console_scripts": [
            "stk = stk.cli:stk",
            "cfn = stk.cli:stk",
        ]
    },
)
