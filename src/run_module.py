
from argparse import ArgumentParser
from datetime import datetime as dt
from pytz import utc
from subprocess import check_call, CalledProcessError
from tempfile import TemporaryDirectory

from cd import cd
from conf import *
import git
from run import run, success


def load_config_paths(file):
    path = Path(file)
    if path.exists():
        with path.open('r') as f:
            paths = [ Path(line[:-1]) for line in f.readlines() ]
            print('Found paths in file %s:\n\t%s' % (file, '\n\t'.join(paths)))
            return paths

    return []


def clone_and_run_module(path, dir=None, runs_path=None, upstream_branch=None, lock_timeout_s=600, keep_tmpdir=False):
    if not dir:
        if keep_tmpdir:
            dir = TemporaryDirectory().name
        else:
            with TemporaryDirectory() as dir:
                return clone_and_run_module(path, dir, runs_path, upstream_branch, lock_timeout_s)

    dir  = Path( dir).absolute().resolve()
    path = Path(path).absolute().resolve()

    with cd(path):
        git.allow_pushes()

    if not runs_path:
        # Log runs of this module in RUNS_DIR ('runs/') by default
        runs_path = path / RUNS_DIR

    runs_path = runs_path.absolute().resolve()

    if not runs_path.exists():
        # Initialize fresh runs/ dir from current state of repo
        run([ 'git', 'clone', path, runs_path])

    with cd(runs_path):
        git.allow_pushes()

    run([ 'git', 'clone', '--depth=1', 'file://%s' % path, dir ])

    with cd(dir):
        remote = git.remote()

        run([ 'git', 'config', 'advice.detachedHead', 'false' ])

        if not upstream_branch:
            upstream_branch = DEFAULT_UPSTREAM_BRANCH
        upstream_remote_branch = '%s/%s' % (remote, upstream_branch)

        original_upstream_sha = git.sha(upstream_remote_branch)
        print('Working from upstream branch %s (%s)' % (upstream_remote_branch, original_upstream_sha))

        base_sha = git.sha()
        if original_upstream_sha != base_sha:
            print('Overriding cloned HEAD %s to start from upstream %s (%s)' % (base_sha, upstream_remote_branch, original_upstream_sha))
            git.checkout(upstream_remote_branch)
            base_sha = original_upstream_sha

        state_paths = load_config_paths(STATE_FILE)
        out_paths = load_config_paths(OUT_FILE)
        if not out_paths:
            out_paths = [ 'out' ]

        run_script = dir / RUN_SCRIPT
        if not run_script.exists():
            raise Exception('No runner script found at %s' % run_script)

        now = dt.now(utc)
        now_str = now.strftime(FMT)

        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        files = [
            OUT_PATH,
            ERR_PATH,
        ] + state_paths + out_paths

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

        if MSG_PATH.exists():
            with MSG_PATH.open('r') as f:
                msg = f.read()
            MSG_PATH.unlink()
        else:
            msg = '%s: %s' % (now_str, status)

        git.add(files)
        run([ 'git', 'commit', '-a', '--allow-empty', '-m', msg ])

        run_sha = git.sha()
        print('Committed run: %s' % run_sha)

        run([ 'git', 'remote', 'add', RUNS_REMOTE, runs_path ])
        git.fetch(RUNS_REMOTE)
        runs_head = '%s/%s' % (RUNS_REMOTE, RUNS_BRANCH)
        runs_sha = git.sha(runs_head, missing_ok=True)

        if not git.exists(RUNS_BRANCH):
            run([ 'git', 'branch', RUNS_BRANCH, run_sha ])
        git.checkout(RUNS_BRANCH)

        if not runs_sha:
            print('%s branch doesn\'t exist on remote %s; created locally with current run SHA: %s' % (RUNS_BRANCH, RUNS_REMOTE, run_sha))
        elif git.is_ancestor(runs_sha, base_sha):
            print('Base SHA %s descends from %s/%s SHA %s; using existing run SHA %s' % (base_sha, RUNS_REMOTE, RUNS_BRANCH, runs_sha, run_sha))
        else:
            if git.is_ancestor(base_sha, runs_sha):
                new_run_sha = git.commit_tree(msg, runs_sha, sha=run_sha)
                print("Changing latest run %s parent from base SHA %s to %s/%s SHA %s; now %s" % (run_sha, base_sha, RUNS_REMOTE, RUNS_BRANCH, runs_sha, new_run_sha))
            else:
                new_run_sha = git.commit_tree(msg, base_sha, runs_sha, sha=run_sha)
                print('Giving latest run %s two parents: base SHA %s and %s/%s SHA %s; now %s' % (run_sha, base_sha, RUNS_REMOTE, RUNS_BRANCH, runs_sha, new_run_sha))

            run_sha = new_run_sha
            run([ 'git', 'reset', '--hard', run_sha ])

        git.push(RUNS_REMOTE, dest=RUNS_BRANCH)

        if state_paths:
            git.checkout_and_reset(original_upstream_sha, None, run_sha, is_branch=False)
            git.add(state_paths)
            if not success('git', 'diff', '--cached', '--quiet'):
                print('Committing state updates')
                msg = '%s: update state' % now_str
                run([ 'git', 'commit', '-m', msg])
                print('Setting parents to base SHA %s and run SHA %s' % (base_sha, run_sha))
                sha = git.commit_tree(msg, base_sha, run_sha)
                git.push(remote, src=sha, dest=upstream_branch)
            else:
                print('No state updates')

    print('Module finished: %s' % path)

if __name__ == '__main__':
    parser = ArgumentParser()
    add_argument = parser.add_argument
    add_argument('url', help='Module Git repo / directory to run')
    add_argument('dir', nargs='?', default=None, help='Local directory to clone into and work in')
    add_argument('runs_url', nargs='?', default=None, help='Local directory to additionally clone module into and record run in')
    add_argument('-l', '--lock_timeout_s', default=600, required=False, help='Timeout (s) for locking git dirs being operated on')
    add_argument('-u', '--upstream_branch', default=None, required=False, help='Override upstream branch to clone (default: master)')
    add_argument('-k', '--keep_tmpdir', default=False, action='store_true', help="If working dir <dir> isn't provided, a temporary working dir will be created. When this flag is set, such a tmpdir will not be removed after the run completes (which can be useful for debugging)")
    args = parser.parse_args()
    clone_and_run_module(
        args.url,
        args.dir,
        args.runs_url,
        upstream_branch=args.upstream_branch,
        keep_tmpdir=args.keep_tmpdir
    )
