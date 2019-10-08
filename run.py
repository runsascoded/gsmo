
from subprocess import check_call, CalledProcessError, DEVNULL


def run(args):
    """Print a command before running it (converting all args to strs as well; useful for Paths in particular)"""
    args = [ str(arg) for arg in args ]
    print('Running: %s' % ' '.join(args))
    check_call(args)


def success(*args):
    try:
        check_call(args, stdout=DEVNULL, stderr=DEVNULL)
        return True
    except CalledProcessError:
        return False
