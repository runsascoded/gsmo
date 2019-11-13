
from subprocess import check_call, check_output, CalledProcessError, DEVNULL


def run(args):
    """Print a command before running it (converting all args to strs as well; useful for Paths in particular)"""
    args = [ str(arg) for arg in args ]
    print('Running: %s' % ' '.join(args))
    check_call(args)


def success(*args, stdout=DEVNULL, stderr=DEVNULL):
    try:
        check_call(args, stdout=stdout, stderr=stderr)
        return True
    except CalledProcessError:
        return False


def output(cmd, stderr=None):
    kwargs = {}
    if stderr:
        kwargs['stderr'] = stderr

    return check_output(cmd, **kwargs).decode()


def lines(cmd, stderr=None, keep_empty_last_line=False):
    out = output(cmd, stderr)
    lines = out.split('\n')
    if lines and lines[-1] == '' and not keep_empty_last_line:
        lines = lines[:-1]
    return lines


_lines = lines
def line(cmd, stderr=None, empty_ok=False):
    lines = _lines(cmd, stderr)
    num_lines = len(lines)
    empty = num_lines == 0
    expected = '0 or 1' if empty_ok else '1'
    if (empty and not empty_ok) or num_lines > 1:
        raise Exception('Found %d lines; expected %s:\n\t%s' % (num_lines, expected, '\n\t'.join(lines)))
    if empty:
        return None
    return lines[0]
