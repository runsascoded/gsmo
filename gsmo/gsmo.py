#!/usr/bin/env python

try:
    import utz
except ImportError:
    from subprocess import check_call
    from sys import executable
    check_call([executable,'-m','pip','install','-u','utz'])


from utz import *

from .config import clean_group, clean_mount

parser = ArgumentParser()
parser.add_argument('input',nargs='?',help='Input directory containing run.ipynb (and optionally config.yaml, or other path specified by "-y"); defaults to current directory')

group = parser.add_mutually_exclusive_group()
group.add_argument('-j','--jupyter',action='store_true',help="Run a jupyter server in the current directory")
group.add_argument('-s','--shell',action='store_true',help="Open a /bin/bash shell in the container (instead of running a jupyter server)")
parser.add_argument('-a','--apt',help='Comma-separated list of packages to apt-get install')
parser.add_argument('--commit','--state',nargs='*',help='Paths to `git add` and commit after running')
parser.add_argument('-C','--dir',help="Resolve paths relative to this directory (default: current directory)")
parser.add_argument('-d','--detach',action='store_true',help="When booting into Jupyter server mode, detach the container")
parser.add_argument('--dst',help='Path inside Docker container to mount current directory/repo to (default: /src)')
parser.add_argument('-e','--env',nargs='*',help='Env vars to set when running Docker container')
parser.add_argument('-i','--image',help='Base docker image to build on (default: runsascoded/gsmo)')
parser.add_argument('-g','--group',nargs='*',help='Groups to add user to in the Docker container')
parser.add_argument('-n','--name',help='Container name (defaults to directory basename)')
parser.add_argument('-o','--out',help='Path or directory to write output notebook to (relative to `input` directory; default: "nbs")')
parser.add_argument('-p','--pip',help='Comma-separated (or multi-arg) list of packages to pip install')
parser.add_argument('-P','--port',nargs='*',help='Ports (or ranges) to expose from the container (if Jupyter server is being run, the first port in the first provided range will be used); can be passed multiple times and/or as comma-delimited lists')
parser.add_argument('-R','--skip-requirements-txt',action='store_true',help="Skip {reading,`pip install`ing} any requirements.txt that is present")
parser.add_argument('-t','--tag',help='Comma-separated (or multi-arg) list of tags to add to built docker image')
parser.add_argument('-U','--root','--no-user',action='store_true',help="Run docker as root (instead of as the current system user)")
parser.add_argument('-v','--mount',nargs='*',help='Paths to mount into Docker container; relative paths are accepted, and the destination can be omitted if it matches the src (relative to the current directory, e.g. "home" → "/home")')
parser.add_argument('-y','--config-yaml',help='YAML file with default configuration settings (default: {gsmo,config}.{yml,yaml})')

args = parser.parse_args()

DEFAULT_IMAGE = 'runsascoded/gsmo'
DEFAULT_CONFIG_STEMS = ['gsmo','config']
CONFIG_XTNS = ['yaml','yml']
DEFAULT_SRC_MOUNT_DIR = '/src'

config_paths = [
    f
    for stem in DEFAULT_CONFIG_STEMS
    for xtn in CONFIG_XTNS
    if exists(f := f'{stem}.{xtn}')
]

if config_paths:
    config_path = singleton(config_paths)
    import yaml
    with open(config_path,'r') as f:
        config = o(yaml.load(f))
else:
    config = o()

def lists(args, sep=','):
    if args is None:
        return []

    if isinstance(args, str):
        args = [ args ]

    return [
        a
        for arg in args
        for a in arg.split(sep)
    ]

def get(keys, default=None):
    if isinstance(keys, str):
        keys = [keys]

    for k in keys:
        if hasattr(args, k):
            if v := getattr(args, k) is not None:
                return v

    for k in keys:
        if k in config:
            print(f'Found config {k}')
            return config[k]

    return default

dir = args.dir
if dir:
    print(f'Running in: {dir}')
    chdir(dir)


cwd = getcwd()
input = args.input or cwd


dst = get('dst',DEFAULT_SRC_MOUNT_DIR)

envs = get('env', [])
if isinstance(envs, (list, tuple)):
    envs = dict([
        env.split('=', 1)
        for env in envs
    ])
elif envs is not None and not isinstance(envs, dict):
    raise ValueError(f'Unexpected env dict: {envs}')

commit = lists(get('commit'))
base_image = get('image', DEFAULT_IMAGE)
image = base_image

groups = lists(get('group'))
groups = [ clean_group(group) for group in groups ]

out = get('out') or 'nbs'

mounts = lists(get('mount', []))
print(f'mounts: {mounts}')
mounts = [ clean_mount(mount) for mount in mounts ]
mounts += [ f'{cwd}:{dst}', ]

ports = get('port')
apts = lists(get('apt'))
pips = lists(get('pip'))
tags = lists(get('tag'))
name = get('name', default=basename(input))
skip_requirements_txt = args.skip_requirements_txt
root = get('root')

jupyter = args.jupyter
jupyter_port = None

detach = args.detach
if detach:
    if not jupyter:
        raise ValueError(f'-d/--detach only applicable to -j/--jupyter mode')

shell = args.shell


if ports:
    # Flatten comma-delimited lists
    ports = [ arg for port in ports for arg in port.split(',') ]
    port = ports[0]
    port_pcs = port.split('-')
    if len(port_pcs) == 1:
        jupyter_port = port
    elif len(port_pcs) == 2:
        jupyter_port = port_pcs[0]
    else:
        raise ValueError(f'Unrecognized port/range: {port}')
else:
    if jupyter:
        # Hash the module name to determine a port for Jupyter
        start = 2**10
        end = 2**16
        from hashlib import sha256
        m = sha256()
        m.update(name.encode())
        digest = int(m.hexdigest(), 16)
        jupyter_port = digest % (end-start) + start
        ports = [ f'{jupyter_port}:{jupyter_port}', ]
    else:
        ports = []


with TemporaryDirectory() as dir:
    # If this becomes true, write out a fresh Dockerfile (to `tmp_dockerfile`) and build an image
    # based from it; otherwise, use an extant upstream image
    docker = False
    tmp_dockerfile = join(dir, 'Dockerfile')

    dockerfile = join(cwd, 'Dockerfile')
    if exists(dockerfile):
        docker = True
        copy(dockerfile, tmp_dockerfile)

    def write(*lines):
        global docker
        if not docker:
            docker = True
            write(f'FROM {base_image}')
        with open(tmp_dockerfile, 'a') as f:
            for line in lines:
                f.write(f'{line}\n')

    if apts:
        write(f'RUN apt-get update && apt-get install {" ".join(apts)}')

    reqs_txt = join(cwd, 'requirements.txt')
    if exists(reqs_txt) and not skip_requirements_txt:
        with open(reqs_txt, 'r') as f:
            pips += [ line.rstrip('\n') for line in f.readlines() if line ]

    if pips:
        write(f'RUN pip install {" ".join(pips)}')

    if docker:
        run('docker','build','-t',name,'-f',tmp_dockerfile,cwd)
        image = name

# Determine user to run as (inside Docker container)
if root:
    user_args = []
else:
    uid = line('id','-u')
    gid = line('id','-g')
    user_args = [ '-u', f'{uid}:{gid}' ]

# Remove any existing container
if check('docker','container','inspect',name):
    run('docker','container','rm',name)

flags = [ '-it' ]
if shell:
    # Launch Bash shell
    entrypoint = '/bin/bash'
    args = []
elif jupyter:
    # Launch `jupyter notebook` server
    entrypoint = 'jupyter'
    assert jupyter_port
    args = [
        'notebook',
        '--ip','0.0.0.0',
        '--port',jupyter_port,
        '--ContentsManager.allow_hidden=True',
    ]
    if root:
        args += [ '--allow-root', ]
else:
    entrypoint = 'utz.sh'
    args = [ 'run.ipynb', out, ]


# Get Git user name/email, propagate into image
user = o(
    name  = line('git','config','user.name'),
    email = line('git','config','user.email'),
)

# Set up author info for git committing
envs = {
    **envs,
   'HOME': '/home',
   'GIT_AUTHOR_NAME'    : user.name,
   'GIT_AUTHOR_EMAIL'   : user.email,
   'GIT_COMMITTER_NAME' : user.name,
   'GIT_COMMITTER_EMAIL': user.email,
}

# Build Docker CLI args
env_args = [ [ '-e', f'{k}={v}' ] for k, v in envs.items() ]
mount_args = [ [ '-v', mount ] for mount in mounts ]
port_args = [ [ '-p', port ] for port in ports ]
group_args = [ [ '--group-add', group ] for group in groups ]
entrypoint_args = [ '--entrypoint', entrypoint ]

all_args = \
    flags + \
    entrypoint_args + \
    env_args + \
    mount_args + \
    port_args + \
    user_args + \
    group_args + \
    [image] + \
    args


def main():
    if jupyter and check('which','open'):
        # 1. run docker container in detached mode
        # 2. parse+open jupyter token URL in browser (try every 1s)
        # 3. re-attach container
        run(
            'docker','run',
            '-w',dst,
            '-d',
            '--name',name,
            all_args,
        )
        while True:
            lns = lines('docker','exec',name,'jupyter','notebook','list')
            if lns[0] != 'Currently running servers:':
                raise Exception('Unexpected `jupyter notebook list` output:\n\t%s' % "\n\t".join(lns))
            if len(lns) == 2:
                line = lns[1]
                rgx = f'(?P<url>http://0\.0\.0\.0:(?P<port>\d+)/\?token=(?P<token>[0-9a-f]+)) :: {dst}'
                if not (m := match(rgx, line)):
                    raise RuntimeError(f'Unrecognized notebook server line: {line}')
                if m['port'] != str(jupyter_port):
                    raise RuntimeError(f'Jupyter running on unexpected port {m["port"]} (!= {jupyter_port})')
                token = m['token']
                url = f'http://127.0.0.1:{jupyter_port}?token={token}'
                run('open',url)
                if not detach:
                    run('docker','attach',name)
                break
            else:
                SLEEP_INTERVAL = 1
                print(f'No Jupyter server found in container {name}; sleep {SLEEP_INTERVAL}s…')
                sleep(SLEEP_INTERVAL)
    else:
        run(
            'docker','run',
            '-w',dst,
            '--name',name,
            all_args,
        )


if __name__ == '__main__':
    main()
