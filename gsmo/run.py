#!/usr/bin/env python

from argparse import ArgumentParser
from os import chdir
from os.path import exists


parser = ArgumentParser()
parser.add_argument('nbs',nargs='*',help='Optional: notebook to run, output path; default: "run.ipynb"')
parser.add_argument('--cwd',action='store_true',help="When set, run from the current dir (by default, the nb's parent dir is used)")
parser.add_argument('--progress',action='store_true',help="When set, have papermill show progress bars")
parser.add_argument('-d','--dir',help="Resolve paths relative to this directory")
parser.add_argument('-f','--file',help='YAML file with parameters to pass to notebook <nb>')
parser.add_argument('-y','--yaml',help='YAML string with parameters to pass to notebook <nb>')
parser.add_argument('-j','--json',help='JSON string with parameters to pass to notebook <nb>')
args = parser.parse_args()
nbs = args.nbs
out = None
if len(nbs) == 0:
    nb = 'run.ipynb'
elif len(nbs) == 1:
    [nb] = nbs
elif len(nbs) == 2:
    [nb,out] = nbs
else:
    raise ValueError(f'Too many positional args (max 2; input+output): {nbs}')

cwd = args.cwd
progress_bar = args.progress
dir = args.dir
if dir: chdir(dir)

file = args.file
yaml_str = args.yaml
json_str = args.json

params = {}

if not file and exists('run.yml'):
    file = 'run.yml'

if file:
    import yaml
    with open(file,'r') as f:
        params = { **yaml.safe_load(f), **params }

if yaml_str:
    import yaml
    params = { **yaml.safe_load(yaml_str), **params }

if json_str:
    import json
    params = { **json.loads(json_str), **params }


from .papermill import execute

execute(
    input=nb,
    output=out,
    cwd=cwd,
    progress_bar=progress_bar,
    **params
)
