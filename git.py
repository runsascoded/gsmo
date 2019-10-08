
from pathlib import Path
from run import success
from subprocess import check_output

def git_sha():
    return check_output([ 'git', 'log', '--no-walk', '--format=%h' ]).decode().strip()


def is_git_ignored(path):
    return success('git', 'check-ignore', '-q', str(path))


def ensure_git_ignored(path):
    path = Path(path)
    if not is_git_ignored(path):
        with open('.gitignore', 'a') as f:
            with open('.gitignore', 'a') as f:
                f.write('%s\n' % str(path))


