from setuptools import setup

setup(
    entry_points={
        'console_scripts': [ "stk =  stk.cli:stk" ]
    }
)
