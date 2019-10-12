
from pathlib import Path
from run import line, lines, output, run, success
from subprocess import CalledProcessError, check_call, check_output, DEVNULL

def sha(*args):
    return check_output([ 'git', 'log', '--no-walk', '--format=%h' ] + list(args)).decode().strip()


def is_git_ignored(path):
    return success('git', 'check-ignore', '-q', str(path))


def ensure_git_ignored(path):
    path = Path(path)
    if not is_git_ignored(path):
        with open('.gitignore', 'a') as f:
            with open('.gitignore', 'a') as f:
                f.write('%s\n' % str(path))


def tree(*args):
    return check_output([ 'git', 'log', '--no-walk', '--format=%T' ] + list(args)).decode().strip()


def commit_tree(msg, *parents):
    tree_sha = tree()
    check_call([ 'git', 'commit-tree', tree_sha ] + parents + [ '-m', msg ])


def is_ancestor(ancestor, descendent):
    return success('git', 'merge-base', '--is-ancestor', ancestor, descendent)


def get_upstream(default=None):
    cmd = [ 'git', 'log', '--no-walk', '--format=%h', '@{u}' ]
    if default:
        try:
            return check_output(cmd, stderr=DEVNULL).decode().strip()
        except CalledProcessError:
            return default

    return check_output(cmd).decode().strip()


def checkout(branch, default_sha=None, return_sha=True):
    if not success('git', 'show-branch', branch):
        if not default_sha:
            raise Exception('Branch %s not found, and no default SHA provided' % branch)
        run([ 'git', 'branch', branch, default_sha ])
        run([ 'git', 'checkout', branch ])
        return default_sha

    run([ 'git', 'checkout', branch ])
    if return_sha:
        return sha()
    return None


def checkout_and_reset(branch, default_sha, new_tree):
    """Force the working tree to match `new_tree` while the branch points to `default_sha`.

    After creating the branch if necessary, leaves staged/unstaged changes ready to be committed,
    simulating an in-progress cherry-pick of `new_tree` on top of the branch's current SHA.
    """
    current_sha = checkout(branch, default_sha)
    run([ 'git', 'reset', '--hard', new_tree ])
    run([ 'git', 'reset', current_sha ])
    return current_sha


def remote(name=None):
    if name is None:
        return line([ 'git', 'remote' ])

    return line([ 'git', 'remote', 'get-url', name ])
