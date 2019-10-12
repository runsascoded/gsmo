
from subprocess import check_call, check_output, CalledProcessError, DEVNULL


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


def output(cmd, stderr=None):
    kwargs = {}
    if stderr:
        kwargs['stderr'] = stderr

    return check_output(cmd, **kwargs).decode()


def lines(cmd, stderr=None):
    out = output(cmd, stderr)
    return [ line[:-1] for line in out.split('\n') ]


def line(cmd, stderr=None, empty_ok=False):
    _lines = lines(cmd, stderr)
    num_lines = len(_lines)
    empty = num_lines == 0 or _lines == ['']
    expected = '0 or 1' if empty_ok else '1'
    if (empty and not empty_ok) or num_lines > 1:
        raise Exception('Found %d lines; expected %s:\n%s' % (num_lines, expected, '\n\t'.join(_lines)))
    if empty:
        return None
    return _lines[0]
