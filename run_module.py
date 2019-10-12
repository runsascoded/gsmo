
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
        force_upstream_branch = True
        if not upstream_branch:
            upstream_branch = DEFAULT_UPSTREAM_BRANCH
            force_upstream_branch = False
        upstream_remote_branch = '%s/%s' % (remote, upstream_branch)

        original_upstream_sha = git.sha(upstream_remote_branch)
        sha = git.sha()
        if original_upstream_sha != sha and force_upstream_branch:
            print('Overriding cloned SHA %s to start from upstream %s (%s)' % (sha, upstream_remote_branch, original_upstream_sha))
            git.checkout(original_upstream_sha)
            sha = original_upstream_sha

        upstream_base_sha = sha

        state_branch = None
        state_paths = load_state_paths()
        if state_paths:
            state_branch = line([ 'git', 'for-each-ref', '--format=%(refname:short)', '--points-at=%s' % sha, STATE_BRANCH_PREFIX ], empty_ok=True)
            if state_branch:
                state_branch_sha = git.sha(state_branch)
                upstream_base_sha = state_branch[len(STATE_BRANCH_PREFIX):]

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
            git.fetch(dir, path)

            runs_branch = RUNS_BRANCH_PREFIX + upstream_base_sha
            prev_runs_branch_sha = git.checkout_and_reset(runs_branch, upstream_base_sha, run_sha)

            run([ 'git', 'add' ] + files)
            run([ 'git', 'commit', '-a', '--allow-empty', '-m', msg])

            if state_branch_sha and not git.is_ancestor(state_branch_sha, runs_branch):
                print(
                    'Rewriting commit as a merge of runs branch (%s: %s) and parent state %s' % (runs_branch, prev_runs_branch_sha, state_branch_sha)
                )
                parents = [ state_branch_sha, prev_runs_branch_sha ]
                git.commit_tree(msg, *parents)

    if state_paths:
        print('Checking for state updates in %s' % path)
        with cd(path):
            with lock(LOCK_FILE_NAME, lock_timeout_s):
                git.fetch(runs_path, dir)

                if not state_branch:
                    state_branch = STATE_BRANCH_PREFIX + upstream_base_sha

                upstream_branch_sha = git.sha(upstream_branch)
                # new_upstream_sha = git.checkout_and_reset(upstream_branch, None, run_sha)

                if upstream_branch_sha != original_upstream_sha:
                    original_state_branch_sha = git.checkout(state_branch, original_upstream_sha)
                    run([ 'git', 'add' ] + state_paths)
                    if not success('git', 'diff', '--cached', '--quiet'):
                        print('Committing state updates')
                        msg = '%s: update state' % now_str
                        run([ 'git', 'commit', '-m', msg])
                    else:
                        print('No state upstead')
                    stderr.write('Upstream branch %s seems to have moved since run started: originally %s, now %s; adding run commit %s to %s branch' % (
                        upstream_branch,
                        original_upstream_sha,
                        upstream_branch_sha,
                        run_sha,
                        state_branch
                    ))
                else:

                HEAD = new_upstream_sha
                run([ 'git', 'add' ] + state_paths)
                # run([ 'git', 'add', '-u', '.'])
                if not success('git', 'diff', '--cached', '--quiet'):
                    print('Committing state updates')
                    msg = '%s: update state' % now_str
                    run([ 'git', 'commit', '-m', msg])
                    HEAD = git.sha()
                    if new_upstream_sha != original_upstream_sha:
                        stderr.write('Upstream branch %s seems to be getting clobbered: originally %s, then %s, coercing to %s (final SHA: %s)' % (
                            upstream_branch,
                            original_upstream_sha,
                            new_upstream_sha,
                            run_sha,
                            HEAD
                        ))
                else:
                    print('No state updates found')

                print('Setting state branch %s to HEAD (%s)' % (state_branch, HEAD))
                run([ 'git', 'reset', '--hard', 'HEAD' ])
                run([ 'git', 'branch', '-f', state_branch, 'HEAD' ])


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
