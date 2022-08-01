import os
from contextlib import contextmanager


@contextmanager
def chdir(path):
    pwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(pwd)
