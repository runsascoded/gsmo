from gsmo import control
from .modules import Modules
from .papermill import execute
from . import gsmo

def OK(msg, throw=True):
    exc = control.OK(msg)
    if throw:
        raise exc
    else:
        return exc


from .config import version
__version__ = version
