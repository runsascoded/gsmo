from . import control
from .modules import Modules
from .papermill import execute

def OK(msg, throw=True):
    exc = control.OK(msg)
    if throw:
        raise exc
    else:
        return exc
