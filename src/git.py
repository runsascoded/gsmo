
from pathlib import Path
from run import line, run, success
from subprocess import CalledProcessError, check_output, DEVNULL

def sha(*args, missing_ok=False):
    cmd = [ 'git', 'log', '--no-walk', '--format=%h' ] + list(args) + [ '--' ]
    if missing_ok:
        try:
            output = check_output(cmd, stderr=DEVNULL)
        except CalledProcessError:
            return None
    else:
        output = check_output(cmd)

    return output.decode().strip()


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


_sha = sha
def commit_tree(msg, *parents, sha=None):
    if sha:
        tree_sha = tree(sha)
    else:
        tree_sha = tree()
    parent_args = [
        arg
        for parent in parents
        for arg in [ '-p', parent ]
    ]
    sha = line([ 'git', 'commit-tree', tree_sha, '-m', msg ] + parent_args)
    return sha


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


def checkout(branch, default_sha=None, return_sha=True, is_branch=True):
    if is_branch and not success('git', 'show-branch', branch):
        if not default_sha:
            raise Exception('Branch %s not found, and no default SHA provided' % branch)
        run([ 'git', 'branch', branch, default_sha ])
        run([ 'git', 'checkout', branch ])
        return default_sha

    run([ 'git', 'checkout', branch ])
    if return_sha:
        return sha()
    return None


def checkout_and_reset(branch, default_sha, new_tree, is_branch=True):
    """Force the working tree to match `new_tree` while the branch points to `default_sha`.

    After creating the branch if necessary, leaves staged/unstaged changes ready to be committed,
    simulating an in-progress cherry-pick of `new_tree` on top of the branch's current SHA.
    """
    current_sha = checkout(branch, default_sha, is_branch=is_branch)
    run([ 'git', 'reset', '--hard', new_tree ])
    run([ 'git', 'reset', current_sha ])
    return current_sha


def fetch(*remotes):
    for remote in remotes:
        run([ 'git', 'fetch', remote ])


def remote(name=None):
    if name is None:
        return line([ 'git', 'remote' ])

    return line([ 'git', 'remote', 'get-url', name ])


def allow_pushes():
    run([ 'git', 'config', 'receive.denyCurrentBranch', 'ignore' ])


def exists(refspec):
    return success('git', 'show-branch', refspec)


def push(remote, src=None, dest=None):
    if dest is None or src == dest:
        dest = src
        refspec = dest
    else:
        if src is None and dest is not None:
            src = 'HEAD'
        refspec = '%s:%s' % (src, dest)

    cmd = [ 'git', 'push', remote, refspec ]
    try:
        run(cmd)
    except CalledProcessError:
        print('Failed to push %s/%s; attempting a merge:' % (remote, refspec))
        run([ 'git', 'merge', '-X', 'ours', '--no-edit', '%s/%s' % (remote, dest) ])
        print('Trying to push again:')
        run(cmd)


def add(files, *args):
    paths = [ file for file in files if Path(file).exists() ]
    if paths:
        run([ 'git', 'add' ] + list(args) + [ '--' ] + paths)
