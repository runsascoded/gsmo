from os import chdir, getcwd
from pathlib import Path


class cd:
    """Context manager for changing the current working directory"""
    def __init__(self, path):
        path = Path(path)
        self.path = path.expanduser()

    def __enter__(self):
        self.prevPath = Path(getcwd())
        chdir(str(self.path))

    def __exit__(self, etype, value, traceback):
        chdir(str(self.prevPath))
