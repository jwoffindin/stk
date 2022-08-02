from distutils.core import setup

setup(
    name="stk",
    description="Opinionated CloudFormation deployments",
    license="MIT",
    author="John Woffindin <j.woffindin@gmail.com>",
    version="0.0.1",
    url="https://github.com/jwoffindin/stk",
    install_requires=["setuptools", "click", "boto3", "pyyaml", "jinja2", "rich", "cfn-flip", "gitpython", "git-url-parse"],
    entry_points={
        "console_scripts": [
            "stk = stk.cli:stk",
            "cfn = stk.cli:stk",
        ]
    },
)
