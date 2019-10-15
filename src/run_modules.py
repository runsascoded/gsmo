
from argparse import ArgumentParser
from os import environ as env
from pathlib import Path
from tempfile import mkdtemp, TemporaryDirectory

from conf import CRON_MODULE_RC_ENV, CRON_MODULE_RC
from run_module import clone_and_run_module


def run_module(url, preserve_tmp_clones, runs_url=None):
    if preserve_tmp_clones:
        dir = mkdtemp()
        clone_and_run_module(url, dir, runs_url)
    else:
        with TemporaryDirectory() as dir:
            clone_and_run_module(url, dir, runs_url)


def load_modules():
    """Attempt to load a modules list from a file ($CRON_MODULE_RC env var, if set, otherwise ~/.cron-module-rc)"""
    cron_module_rc_path = None
    if CRON_MODULE_RC_ENV in env:
        cron_module_rc_path = env[CRON_MODULE_RC_ENV]
    else:
        home = Path(env['HOME'])
        default_cron_module_rc = home / CRON_MODULE_RC
        if default_cron_module_rc.exists():
            cron_module_rc_path = default_cron_module_rc

    if cron_module_rc_path is None:
        raise Exception('No arguments passed, %s env var set, or %s found' % (CRON_MODULE_RC_ENV, CRON_MODULE_RC))

    with cron_module_rc_path.open('r') as f:
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
