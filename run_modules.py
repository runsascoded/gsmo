
from argparse import ArgumentParser
from datetime import datetime as dt
from fcntl import flock, LOCK_EX, LOCK_NB
from os import environ as env
from pathlib import Path
from pytz import utc
from os import chdir, getcwd
from os.path import join, exists
from subprocess import check_call, check_output, CalledProcessError, DEVNULL
from tempfile import mkdtemp, TemporaryDirectory
from urllib.parse import urlparse


FMT= '%Y-%m-%dT%H:%M:%S'
RUN_SCRIPT = 'run.sh'
RUNS_DIR = 'runs'
SUCCESS_PATH = 'SUCCESS'
FAILURE_PATH = 'FAILURE'
LOGS_DIR = 'logs'
OUT_PATH = 'out'
ERR_PATH = 'err'
LOCK_FILE_NAME = '.LOCK'


class cd:
    """Context manager for changing the current working directory"""
    def __init__(self, path):
        path = Path(path)
        self.path = path.expanduser()

    def __enter__(self):
        self.prevPath = Path(getcwd())
        chdir(str(self.path))

    def __exit__(self, etype, value, traceback):
        chdir(str(self.prevPath))


def run(args):
    args = [ str(arg) for arg in args ]
    print('Running: %s' % ' '.join(args))
    check_call(args)


def run_module(url, preserve_tmp_clones, runs_url=None):
    print('module %s, preserve: %s' % (url, preserve_tmp_clones))
    if preserve_tmp_clones:
        dir = mkdtemp()
        clone_and_run_module(url, dir, runs_url)
    else:
        with TemporaryDirectory() as dir:
            clone_and_run_module(url, dir, runs_url)


def git_sha():
    return check_output([ 'git', 'log', '--no-walk', '--format=%h' ]).decode().strip()


def success(*args):
    try:
        check_call(args, stdout=DEVNULL, stderr=DEVNULL)
        return True
    except CalledProcessError:
        return False


def is_git_ignored(path):
    return success('git', 'check-ignore', '-q', str(path))


def ensure_git_ignored(path):
    path = Path(path)
    if not is_git_ignored(path):
        with open('.gitignore', 'a') as f:
            with open('.gitignore', 'a') as f:
                f.write('%s\n' % str(path))


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

        logs_dir = Path(LOGS_DIR)
        logs_dir.mkdir(parents=True, exist_ok=True)

        out_path = logs_dir / OUT_PATH
        err_path = logs_dir / ERR_PATH

        files = [
            out_path,
            err_path,
        ]

        cmd = [ str(run_script) ]
        with out_path.open('w') as out, err_path.open('w') as err:
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
            runs_url = join(url, RUNS_DIR)
            if not exists(runs_url):
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
                except BlockingIOError:
                    print('Failed to lock %s; returning' % lock_file)

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
        # TODO: align branches etc. correctly
        run([ 'git', 'push', runs_url ])


def load_modules():
    """Attempt to load a modules list from a file ($CRON_MODULE_RC env var, if set, otherwise ~/.cron-module-rc)"""
    cron_module_rc_path = None
    if 'CRON_MODULE_RC' in env:
        cron_module_rc_path = env['CRON_MODULE_RC']
    else:
        default_cron_module_rc = join(env['HOME'], '.cron-module-rc')
        if exists(default_cron_module_rc):
            cron_module_rc_path = default_cron_module_rc

    if cron_module_rc_path is None:
        raise Exception('No arguments passed, $CRON_MODULE_RC set, or .cron-module-rc found')

    with open(cron_module_rc_path, 'r') as f:
        return [ line.strip() for line in f.readlines() ]


def main(modules=None, preserve_tmp_clones=False):
    """Main entrypoint; if called with no args, will attempt to parse a module list from the environment"""
    if not modules:
        modules = load_modules()

    errors = []
    for module in modules:
        try:
            run_module(module, preserve_tmp_clones)
        except Exception as e:
            errors.append((module, e))

    if errors:
        raise Exception(errors)


if __name__ == '__main__':
    """Parse cmdline args and delegate to main()"""
    parser = ArgumentParser()
    parser.add_argument('--preserve_tmp_clones', '-p', default=False, action='store_true', help="When true, don't clean up the temporary clones of modules that are run (useful for debugging)")
    parser.add_argument('modules', nargs='+', help='Paths to "modules" to run; each should be a git repository with a "run.sh" script')
    args = parser.parse_args()
    main(args.modules, args.preserve_tmp_clones)
