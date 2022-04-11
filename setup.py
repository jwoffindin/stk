from setuptools import setup

setup(
    name="cfn-stack",
    version='0.0.0',
    packages=("stk", "stk.cli"),
    license="MIT",
    author="John Woffindin",
    description="Opinionated CloudFormation Deployments",
    options = {
    },
    entry_points={
        'console_scripts': [ "stk =  stk.cli:stk" ]
    }
)
