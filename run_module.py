
from argparse import ArgumentParser
from datetime import datetime as dt
from fcntl import flock, LOCK_EX, LOCK_NB
from pytz import utc
from subprocess import check_call, CalledProcessError
from sys import stderr

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


def clone_and_run_module(path, dir, runs_path=None, upstream_branch=None, lock_timeout_s=600):
    dir = Path(dir)

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
        runs_path = Path(path) / RUNS_DIR

    if not runs_path.exists():
        # Initialize fresh runs/ dir from current state of repo
        run([ 'git', 'clone', path, runs_path])

    print('Pulling tmpdir changes into runs repo %s' % runs_path)
    with cd(runs_path):
        with lock(LOCK_FILE_NAME, lock_timeout_s):
            run([ 'git', 'fetch', '--multiple', dir, path ])

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
                else:
                    print('No state updates found')
                    run([ 'git', 'reset', '--hard', state_branch_sha ])


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('url', help='Module Git repo / directory to run')
    parser.add_argument('dir', help='Local directory to clone into and work in')
    parser.add_argument('runs_url', required=False, default=None, help='Local directory to additionally clone module into and record run in')
    args = parser.parse_args()
    clone_and_run_module(args.url, args.dir, args.runs_url)
