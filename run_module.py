
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
from run import line, lines, run, success


def load_state_paths():
    path = Path(STATE_FILE)
    if path.exists():
        with path.open('r') as f:
            return [ line[:-1] for line in f.readlines() ]

    return []


def clone_and_run_module(path, dir=None, runs_path=None, upstream_branch=None, lock_timeout_s=600):
    if not dir:
        with TemporaryDirectory() as dir:
            return clone_and_run_module(path, dir, runs_path, upstream_branch, lock_timeout_s)

    dir  = Path( dir).absolute().resolve()
    path = Path(path).absolute().resolve()

    run([ 'git', 'clone', path, dir])

    with cd(dir):

        remote = git.remote()
        if not upstream_branch:
            upstream_branch = DEFAULT_UPSTREAM_BRANCH
        upstream_branch = '%s/%s' % (remote, upstream_branch)

        run_base_sha = git.sha()
        upstream_base_sha = None

        state_branch = None
        state_branch_base = None
        state_paths = load_state_paths()
        if state_paths:
            state_branch = line([ 'git', 'for-each-ref', '--format=%(refname:short)', '--points-at=%s' % run_base_sha, STATE_BRANCH_PREFIX ], empty_ok=True)
            if state_branch:
                state_branch_base = state_branch[len(STATE_BRANCH_PREFIX):]
                upstream_base_sha = state_branch_base
                if not git.is_ancestor(upstream_branch, state_branch_base):
                    print('Upstream %s contains commits not on state-branch %s; starting a new runs-branch from %s' % (upstream_branch, state_branch_base, upstream_branch))
                    state_branch = None
                    state_branch_base = None
                    run_base_sha = git.checkout(upstream_branch)
                    upstream_base_sha = run_base_sha
            else:
                # If there's no active "state" branch, make sure we're starting from the intended upstream branch.
                # This will be whatever branch the `path` repo is currently on, unless an explicit override `upstream_branch` was passed
                upstream_base_sha = git.sha(upstream_branch)
                if upstream_base_sha != run_base_sha:
                    print('Overriding cloned SHA %s to start from upstream %s (%s)' % (run_base_sha, upstream_branch, upstream_base_sha))
                    git.checkout(upstream_branch, return_sha=False)
                    run_base_sha = upstream_base_sha

        run_script = dir / RUN_SCRIPT
        if not run_script.exists():
            raise Exception('No runner script found at %s' % run_script)

        now = dt.now(utc)
        now_str = now.strftime(FMT)

        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        files = [
            OUT_PATH,
            ERR_PATH,
        ] + state_paths

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

            runs_branch = RUNS_BRANCH_PREFIX + upstream_base_sha
            prev_runs_branch_sha = git.checkout_and_reset(runs_branch, upstream_base_sha, run_sha)

            run([ 'git', 'add' ] + files)
            run([ 'git', 'commit', '-a', '--allow-empty', '-m', msg])

            if state_branch_base and \
                state_branch_base != prev_runs_branch_sha and \
                not git.is_ancestor(state_branch_base, runs_branch):
                print(
                    'Rewriting commit as a merge of runs branch (%s: %s) and parent state %s' % (runs_branch, prev_runs_branch_sha, state_branch_base)
                )
                parents = [ state_branch_base, prev_runs_branch_sha ]
                git.commit_tree(msg, *parents)

    if state_paths:
        print('Checking for state updates in %s' % path)
        with cd(path):
            with lock(LOCK_FILE_NAME, lock_timeout_s):
                run([ 'git', 'fetch', runs_path ])
                run([ 'git', 'fetch', dir ])

                if not state_branch:
                    state_branch = STATE_BRANCH_PREFIX + upstream_base_sha

                state_branch_sha = git.checkout_and_reset(state_branch, upstream_base_sha, run_sha)

                run([ 'git', 'add' ] + state_paths)
                # run([ 'git', 'add', '-u', '.'])
                if not success('git', 'diff', '--cached', '--quiet'):
                    print('Committing state updates')
                    msg = '%s: update state' % now_str
                    run([ 'git', 'commit', '-m', msg])
                    #run([ 'git', 'reset', '--hard', 'HEAD'])
                    if state_branch_base and state_branch_base != state_branch_sha:
                        stderr.write('State branch %s seems to be getting clobbered: originally %s, then %s, coercing to %s (final SHA: %s)' % (
                            state_branch,
                            state_branch_base,
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
    add_argument('-u', '--upstream_branch', default=None, required=False, help='Override upstream branch to anchor %s and %s branches to (for stateful modules)' % (RUNS_BRANCH_PREFIX, STATE_BRANCH_PREFIX))
    args = parser.parse_args()
    clone_and_run_module(args.url, args.dir, args.runs_url)
