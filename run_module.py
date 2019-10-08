
from argparse import ArgumentParser
from datetime import datetime as dt
from fcntl import flock, LOCK_EX, LOCK_NB
from pytz import utc
from subprocess import check_call, CalledProcessError
from sys import executable as python, stderr
from urllib.parse import urlparse

from cd import cd
from conf import *
from git import git_sha, ensure_git_ignored
from run import run, success


# def run_module(url, dir, runs_url=None):
#     cmd = [ python, __file__, url, dir ]
#     if runs_url:
#         cmd.append(runs_url)
#
#     out_path = Path(dir) / RUNNER_OUT_PATH
#     err_path = Path(dir) / RUNNER_ERR_PATH
#     with out_path.open('w') as out, err_path.open('r') as err:
#         check_call(cmd, stdout=out, stderr=err)


def clone_and_run_module(url, dir, runs_url=None):
    dir = Path(dir)
    parsed = urlparse(url)
    scheme = parsed.scheme

    run([ 'git', 'clone', url, dir ])

    with cd(dir):
        base_sha = git_sha()
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

        run_sha = git_sha()
        print('Commit SHA: %s' % run_sha)

    if not scheme:
        # Module is a local directory (that is also a git repo)
        if not runs_url:
            # Log runs of this module in RUNS_DIR ('runs/') by default
            runs_url = Path(url) / RUNS_DIR
            if not runs_url.exists():
                # Initialize fresh runs/ dir from current state of repo
                run([ 'git', 'clone', url, runs_url ])

                # git-ignore runs/ dir/repo in containing repo
                with cd(url):
                    ensure_git_ignored(RUNS_DIR)

        with cd(runs_url):
            lock_file = Path(LOCK_FILE_NAME)

            if not lock_file.exists():
                lock_file.touch()

            with lock_file.open('r') as lock:
                try:
                    flock(lock, LOCK_EX | LOCK_NB)
                except BlockingIOError as e:
                    stderr.write('Failed to lock %s\n' % lock_file)
                    raise e

                run([ 'git', 'fetch', dir ])

                branch = 'runs-%s' % base_sha

                if not success('git', 'show-branch', branch):
                    run([ 'git', 'branch', branch, base_sha ])

                run([ 'git', 'checkout', branch ])

                # Apply the run commit on top of the branch of commits starting from the same "base" SHA of the underlying
                # module.
                # [Hard-reset to commit] followed by [soft-reset to desired parent] and [commit -a] is an "easy" way to
                # achieve this; it's like a cherry-pick, but that automatically blows away any conflicts and sets the
                # latest/HEAD commit to the cherry-picked commit's version.
                parent_sha = git_sha()
                run([ 'git', 'reset', '--hard', run_sha ])
                run([ 'git', 'reset', parent_sha ])

                run([ 'git', 'add' ] + files)
                run([ 'git', 'commit', '-a', '-m', msg])
    else:
        # TODO: align branches, etc. in remote-pushing case; this probably doesn't work or make sense atm
        # run([ 'git', 'push', runs_url ])
        raise Exception('Remote modules not supported yet')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('url', help='Module Git repo / directory to run')
    parser.add_argument('dir', help='Local directory to clone into and work in')
    parser.add_argument('runs_url', required=False, default=None, help='Local directory to additionally clone module into and record run in')
    args = parser.parse_args()
    clone_and_run_module(args.url, args.dir, args.runs_url)
