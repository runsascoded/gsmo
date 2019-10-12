
from argparse import ArgumentParser
from datetime import datetime as dt
from fcntl import flock, LOCK_EX, LOCK_NB
from pytz import utc
from subprocess import check_call, CalledProcessError
from sys import stderr
from tempfile import TemporaryDirectory

from cd import cd
from conf import *
import git
from lock import lock
from run import run, success


def load_state_paths():
    path = Path(STATE_FILE)
    if path.exists():
        with path.open('r') as f:
            return [ line[:-1] for line in f.readlines() ]

    return None


def clone_and_run_module(path, dir=None, runs_path=None, upstream_branch=None, lock_timeout_s=600):
    if not dir:
        with TemporaryDirectory() as dir:
            return clone_and_run_module(path, dir, runs_path, upstream_branch, lock_timeout_s)

    dir = Path(dir)
    dir = dir.absolute().resolve()

    path = Path(path).absolute().resolve()

    run([ 'git', 'clone', path, dir])

    with cd(dir):

        state_paths = load_state_paths()

        base_sha = git.sha()
        if state_paths:
            if not upstream_branch:
                upstream_branch = git.get_upstream()

            parent_sha = base_sha
            base_sha = git.sha(upstream_branch)

        run_script = dir / RUN_SCRIPT
        if not run_script.exists():
            raise Exception('No runner script found at %s' % run_script)

        now = dt.now(utc)
        now_str = now.strftime(FMT)

        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        files = [
            OUT_PATH,
            ERR_PATH,
        ]

        cmd = [ str(run_script) ]
        with OUT_PATH.open('w') as out, ERR_PATH.open('w') as err:
            print('Running: %s' % run_script)
            try:
                check_call(cmd, stdout=out, stderr=err)
                with open(SUCCESS_PATH, 'w') as f:
                    files.append(SUCCESS_PATH)
                status = 'success'
            except CalledProcessError as e:
                with open(FAILURE_PATH, 'w') as f:
                    f.write('%d\n' % e.returncode)

                status = 'failure'
                files.append(FAILURE_PATH)

        msg = '%s: %s' % (now_str, status)

        run([ 'git', 'add' ] + files)
        run([ 'git', 'commit', '-a', '-m', msg ])

        run_sha = git.sha()
        print('Commit SHA: %s' % run_sha)

    if not runs_path:
        # Log runs of this module in RUNS_DIR ('runs/') by default
        runs_path = path / RUNS_DIR

    runs_path = runs_path.absolute().resolve()

    if not runs_path.exists():
        # Initialize fresh runs/ dir from current state of repo
        run([ 'git', 'clone', path, runs_path])

    print('Pulling tmpdir changes into runs repo %s' % runs_path)
    with cd(runs_path):
        with lock(LOCK_FILE_NAME, lock_timeout_s):
            run([ 'git', 'fetch', dir ])
            run([ 'git', 'fetch', path ])

            runs_branch = 'runs-%s' % base_sha
            runs_branch_sha = git.checkout_and_reset(runs_branch, base_sha, run_sha)

            run([ 'git', 'add' ] + files)
            run([ 'git', 'commit', '-a', '-m', msg])

            if state_paths:
                state_branch_sha = parent_sha
                if state_branch_sha != runs_branch_sha and not git.is_ancestor(state_branch_sha, runs_branch):
                    print(
                        'Rewriting commit as a merge of runs branch (%s: %s) and parent state %s' % (runs_branch, runs_branch_sha, state_branch_sha)
                    )
                    parents = [ state_branch_sha, runs_branch_sha ]
                    git.commit_tree(msg, *parents)

    if state_paths:
        print('Checking for state updates in %s' % path)
        with cd(path):
            with lock(LOCK_FILE_NAME, lock_timeout_s):
                run([ 'git', 'fetch', runs_path ])

                state_branch = 'state-%s' % base_sha
                state_branch_sha = git.checkout_and_reset(state_branch, parent_sha, run_sha)

                run([ 'git', 'add', '-u', ] + state_paths)
                if success([ 'git', 'diff', '--cached', '-q' ]):
                    print('Committing state updates')
                    msg = '%s: update state' % now_str
                    run([ 'git', 'commit', '-m', msg])
                    if parent_sha != state_branch_sha:
                        stderr.write('State branch %s seems to be getting clobbered: originally %s, then %s, resetting to %s (%s)' % (
                            state_branch,
                            parent_sha,
                            state_branch_sha,
                            run_sha,
                            git.sha()
                        ))
                else:
                    print('No state updates found')
                    run([ 'git', 'reset', '--hard', state_branch_sha ])

    print('Module finished: %s' % path)

if __name__ == '__main__':
    parser = ArgumentParser()
    add_argument = parser.add_argument
    add_argument('url', help='Module Git repo / directory to run')
    add_argument('dir', nargs='?', default=None, help='Local directory to clone into and work in')
    add_argument('runs_url', nargs='?', default=None, help='Local directory to additionally clone module into and record run in')
    add_argument('-l', '--lock_timeout_s', default=600, required=False, help='Timeout (s) for locking git dirs being operated on')
    add_argument('-u', '--upstream_branch', default=None, required=False, help='Override upstream branch to anchor runs- and state- branches to (for stateful modules)')
    args = parser.parse_args()
    clone_and_run_module(args.url, args.dir, args.runs_url)
