#!/usr/bin/env python

from argparse import ArgumentParser
from functools import partial
from os import chdir, getcwd

from .cli import run_args, load_run_config
from .config import Config, DEFAULT_RUN_NB, DEFAULT_NB_DIR
from .papermill import execute

def main():
    parser = ArgumentParser()
    parser.add_argument('--progress',action='store_true',help="When set, have papermill show progress bars")
    for arg in run_args:
        parser.add_argument(*arg.args, **arg.kwargs)

    args = parser.parse_args()

    config = Config(args)
    get = partial(Config.get, config)

    nb = get('run', DEFAULT_RUN_NB)
    out = get('out', DEFAULT_NB_DIR)

    run_config = load_run_config(args)
    commit = config.get('commit', True)

    progress_bar = args.progress

    dir = get('dir')
    if dir: chdir(dir)

    execute(
        input=nb,
        output=out,
        cwd=getcwd(),
        progress_bar=progress_bar,
        commit=commit,
        **run_config,
    )

if __name__ == '__main__':
    main()
