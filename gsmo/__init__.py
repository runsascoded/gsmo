from . import control

def OK(msg, throw=True):
    exc = control.OK(msg)
    if throw:
        raise exc
    else:
        return exc
