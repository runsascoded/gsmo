#!/usr/bin/env python

from argparse import ArgumentParser
from os import chdir

from .cli import run_args
from .config import DEFAULT_RUN_NB, DEFAULT_NB_DIR, load_config


parser = ArgumentParser()
parser.add_argument('--progress',action='store_true',help="When set, have papermill show progress bars")
for arg in run_args:
    parser.add_argument(*arg.args, **arg.kwargs)

# parser.add_argument('-C','--dir',help="Run from within this directory (default: current directory)")
# parser.add_argument('--commit',nargs='*',help='Paths to `git add` and commit after running')
# parser.add_argument('-o','--out',help='Path or directory to write output notebook to (relative to `input` directory; default: "nbs")')
# parser.add_argument('-x','--run','--execute',help='Notebook to run (default: run.ipynb)')
# parser.add_argument('-y','--yaml-path',nargs='*',help='Path to a YAML file with configuration settings to pass through to the module being run; "run" mode only')
# parser.add_argument('-Y','--yaml-str',nargs='*',help='YAML string with configuration settings to pass through to the module being run; "run" mode only')
args = parser.parse_args()

nb = get('run', DEFAULT_RUN_NB)
out = get('out', DEFAULT_NB_DIR)

config = load_config(args)

run_config = load_run_config(args)

progress_bar = args.progress

dir = get('dir')
if dir: chdir(dir)

# file = args.file
# yaml_str = args.yaml
# json_str = args.json
#
# params = {}
#
# if yaml_str:
#     import yaml
#     params = { **yaml.safe_load(yaml_str), **params }


from .papermill import execute

def main():
    execute(
        input=nb,
        output=out,
        cwd=cwd,
        progress_bar=progress_bar,
        **run_config,
    )

if __name__ == '__main__':
    main()
