#!/usr/bin/env python

try:
    import utz
except ImportError:
    from subprocess import check_call
    from sys import executable
    check_call([executable,'-m','pip','install','-u','utz'])


from utz import *

from .version import get_version
version = get_version()

DEFAULT_IMAGE = f'runsascoded/gsmo:{version}'
DEFAULT_DIND_IMAGE = f'{DEFAULT_IMAGE}:dind_{version}'

from .config import clean_group, clean_mount

parser = ArgumentParser()
parser.add_argument('input',nargs='?',help='Input directory containing run.ipynb (and optionally config.yaml, or other path specified by "-y"); defaults to current directory')

group = parser.add_mutually_exclusive_group()
group.add_argument('-j','--jupyter',action='store_true',help="Run a jupyter server in the current directory")
group.add_argument('-s','--shell',action='store_true',help="Open a /bin/bash shell in the container (instead of running a jupyter server)")
parser.add_argument('-a','--apt',help='Comma-separated list of packages to apt-get install')
parser.add_argument('--commit','--state',nargs='*',help='Paths to `git add` and commit after running')
parser.add_argument('-C','--dir',help="Resolve paths (e.g. mounts) relative to this directory (default: current directory)")
parser.add_argument('-d','--detach',action='store_true',help="When booting into Jupyter server mode, detach the container")
parser.add_argument('--dind',action='store_true',help="When set, mount /var/run/docker.sock in container (and default to a base image that contains docker installed)")
parser.add_argument('-D','--no-docker',dest='docker',default=True,action='store_false',help="Run in the current shell instead of in Docker")
parser.add_argument('--dst',help='Path inside Docker container to mount current directory/repo to (default: /src)')
parser.add_argument('-e','--env',nargs='*',help='Env vars to set when running Docker container')
parser.add_argument('-i','--image',help=f'Base docker image to build on (default: f{DEFAULT_IMAGE})')
parser.add_argument('-g','--group',nargs='*',help='Groups to add user to in the Docker container')
parser.add_argument('-n','--name',help='Container name (defaults to directory basename)')
parser.add_argument('-o','--out',help='Path or directory to write output notebook to (relative to `input` directory; default: "nbs")')
parser.add_argument('-p','--pip',help='Comma-separated (or multi-arg) list of packages to pip install')
parser.add_argument('-P','--port',nargs='*',help='Ports (or ranges) to expose from the container (if Jupyter server is being run, the first port in the first provided range will be used); can be passed multiple times and/or as comma-delimited lists')
parser.add_argument('--rm','--remove-container',action='store_true',help="Remove Docker container after run (pass `--rm` to `docker run`)")
parser.add_argument('-R','--skip-requirements-txt',action='store_true',help="Skip {reading,`pip install`ing} any requirements.txt that is present")
parser.add_argument('-t','--tag',help='Comma-separated (or multi-arg) list of tags to add to built docker image')
parser.add_argument('-I','--no-interactive',action='store_true',help="Don't run interactively / allocate a TTY (i.e. skip `-it` flags to `docker run`)")
parser.add_argument('-U','--root','--no-user',action='store_true',help="Run docker as root (instead of as the current system user)")
parser.add_argument('-v','--mount',nargs='*',help='Paths to mount into Docker container; relative paths are accepted, and the destination can be omitted if it matches the src (relative to the current directory, e.g. "home" → "/home")')
parser.add_argument('--pip_mount',help='Optionally `pip install -e` a mounted directory inside the container before running the usual entrypoint script')
parser.add_argument('-y','--run-config-yaml-path',help='Path to a YAML file with configuration settings to pass through to the module being run; "run" mode only')
parser.add_argument('-Y','--run-config-yaml-str',help='YAML string with configuration settings to pass through to the module being run; "run" mode only')

args = parser.parse_args()

DEFAULT_CONFIG_STEMS = ['gsmo','config']
CONFIG_XTNS = ['yaml','yml']
DEFAULT_SRC_MOUNT_DIR = '/src'

config_paths = [
    f
    for stem in DEFAULT_CONFIG_STEMS
    for xtn in CONFIG_XTNS
    if exists(f := f'{stem}.{xtn}')
]

run_config = {}
if (run_config_yaml_path := args.run_config_yaml_path):
    import yaml
    with open(run_config_yaml_path,'r') as f:
        run_config = yaml.safe_load(f)

if (run_config_yaml_str := args.run_config_yaml_str):
    import yaml
    run_config = o.merge(run_config, yaml.safe_load(run_config_yaml_str))

if config_paths:
    config_path = singleton(config_paths)
    import yaml
    with open(config_path,'r') as f:
        config = o(yaml.safe_load(f))
else:
    config = o()

if (config_yaml_str := args.run_config_yaml_str):
    config_yaml = yaml.safe_load(config_yaml_str)
    config = o.merge(config, config_yaml)

def lists(args, sep=','):
    if args is None:
        return []

    if isinstance(args, str):
        args = args.split(sep)

    return args

def get(keys, default=None):
    if isinstance(keys, str):
        keys = [keys]

    for k in keys:
        if hasattr(args, k):
            if (v := getattr(args, k)) is not None:
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
src = cwd
git_dir = join(src, '.git')
if isfile(git_dir):
    with open(git_dir,'r') as f:
        [ ln ] = [ l for line in f.readlines() if (l := line.strip()) ]
    rgx = r'^gitdir: (?P<path>.*)$'
    if not (m := match(rgx, ln)):
        raise Exception(f'Unrecognized .git file contents: {ln}')
    path = m['path']
    pcs = path.split(sep)
    workdir = []
    i = 0
    while i < len(pcs) and pcs[i] == '..':
        workdir = [basename(src)] + workdir
        src = dirname(src)
        i += 1
    if i + 2 >= len(pcs) or pcs[i] != '.git' or pcs[i+1] != 'modules':
        raise Exception(f'Expected gitdir path of the form `(../)*.git/modules`; found {path}')
    print(f'workdir: {workdir}')
    workdir = join(dst, *workdir)
    print(f'Parsed ancestor mount for submodule: {src}:{dst}, workdir {workdir}')
else:
    workdir = dst

envs = get('env', [])
if isinstance(envs, (list, tuple)):
    envs = dict([
        env.split('=', 1)
        for env in envs
    ])
elif envs is not None and not isinstance(envs, dict):
    raise ValueError(f'Unexpected env dict: {envs}')

commit = lists(get('commit'))

groups = lists(get('group'))
groups = [ clean_group(group) for group in groups ]

out = get('out') or 'nbs'

mounts = lists(get('mount', []))
print(f'mounts: {mounts}')
mounts = [ clean_mount(mount) for mount in mounts ]
mounts += [ f'{src}:{dst}', ]

dind = get('dind')
if dind:
    default_image = DEFAULT_DIND_IMAGE
    mounts += [ '/var/run/docker.sock:/var/run/docker.sock']
else:
    default_image = DEFAULT_IMAGE
base_image = get('image', default_image)
image = base_image

docker = get('docker', True)
rm = get('remove_container')

ports = lists(get('port'))
apts = lists(get('apt'))
pips = lists(get('pip'))
tags = lists(get('tag'))
name = get('name', default=basename(input))
skip_requirements_txt = args.skip_requirements_txt
root = get('root')

jupyter = args.jupyter
jupyter_src_port = jupyter_dst_port = None

detach = args.detach
if detach:
    if not jupyter:
        raise ValueError(f'-d/--detach only applicable to -j/--jupyter mode')

shell = args.shell
if shell and not docker:
    raise ValueError('`shell` mode not supported when Docker mode is disabled')


if ports:
    # Canonicalize a port argument:
    # - "5432" → "5432:5432"
    # - "8880-8890" → "8880-8890:8880-8890"
    # - "5432:5432" → "5432:5432" (no-op)
    def clean_port(port):
        pcs = port.split(':')
        if len(pcs) == 1:
            port = pcs[0]
            return f'{port}:{port}'
        elif len(pcs) == 2:
            return port
        else:
            raise ValueError(f'Unrecognized port/range: {port}')

    # Flatten and normalize comma-delimited list of port args
    ports = [
        clean_port(arg)
        for port in ports
        for arg in port.split(',')
    ]

    if jupyter:
        [ src_port, dst_port ] = ports[0].split(':')

        src_pcs = src_port.split('-')
        if len(src_pcs) <= 2:
            jupyter_src_port = src_pcs[0]
        else:
            raise ValueError(f'Unrecognized port/range: {src_port}')

        dst_pcs = dst_port.split('-')
        if len(dst_pcs) <= 2:
            jupyter_dst_port = dst_pcs[0]
        else:
            raise ValueError(f'Unrecognized port/range: {dst_port}')
else:
    if jupyter:
        # Hash the module name to determine a port for Jupyter in the range [2**10,2**16)
        start = 2**10
        end = 2**16
        from hashlib import sha256
        m = sha256()
        m.update(name.encode())
        digest = int(m.hexdigest(), 16)
        jupyter_src_port = jupyter_dst_port = digest % (end-start) + start
        ports = [ f'{jupyter_src_port}:{jupyter_dst_port}', ]
    else:
        ports = []


with NamedTemporaryFile(dir='.', prefix='Dockerfile.') as f:
    # If this becomes true, write out a fresh Dockerfile (to `tmp_dockerfile`) and build an image
    # based from it; otherwise, use an extant upstream image
    build_image = False
    tmp_dockerfile = f.name

    dockerfile = join(cwd, 'Dockerfile')
    if exists(dockerfile):
        build_image = True
        copy(dockerfile, tmp_dockerfile)

    def write(*lines, warn_on_no_docker=True):
        global build_image
        if not build_image:
            build_image = True
            write(f'FROM {base_image}')
        if docker:
            with open(tmp_dockerfile, 'a') as f:
                for line in lines:
                    f.write(f'{line}\n')
        elif warn_on_no_docker:
            stderr.write(f'Docker configs skipped in docker-less mode:\n')
            for line in lines:
                stderr.write('\t%s\n' % line)

    if apts:
        write(f'RUN apt-get update && apt-get install -y {" ".join(apts)}')

    reqs_txt = join(cwd, 'requirements.txt')
    if exists(reqs_txt) and not skip_requirements_txt:
        with open(reqs_txt, 'r') as f:
            pips += [ line.rstrip('\n') for line in f.readlines() if line ]

    if pips:
        if docker:
            write(f'RUN pip install {" ".join(pips)}', warn_on_no_docker=False)
        else:
            import pip
            print(f'pip install {" ".join(pips)}')
            pip.main(['install'] + pips)

    if build_image:
        if docker:
            run('docker','build','-t',name,'-f',tmp_dockerfile,cwd)
            image = name

# Determine user to run as (inside Docker container)
user_args = []
if not root:
    uid = line('id','-u')
    if uid == '0':
        root = True
    else:
        gid = line('id','-g')
        user_args = [ '-u', f'{uid}:{gid}' ]

# Remove any existing container
if docker:
    if check('docker','container','inspect',name):
        run('docker','container','rm',name)

interactive = not args.no_interactive
if interactive:
    flags = [ '-it' ]
else:
    flags = []
if rm:
    assert docker
    flags += ['--rm']

if run_config:
    if jupyter or shell:
        raise ValueError(f'Run configs not supported in `jupyter`/`shell` modes')

if shell:
    # Launch Bash shell
    entrypoint = '/bin/bash'
    args = []
elif jupyter:
    # Launch `jupyter notebook` server
    entrypoint = 'jupyter'
    assert jupyter_dst_port
    args = [
        'notebook',
        '--ip','0.0.0.0',
        '--port',jupyter_dst_port,
        '--ContentsManager.allow_hidden=True',
    ]
    if root:
        args += [ '--allow-root', ]
else:
    entrypoint = 'gsmo-entrypoint'
    args = [ 'run.ipynb', out, ]


pip_mounts = lists(get('pip_mount'))
if pip_mounts:
    args = [ len(pip_mounts) ] + pip_mounts + [ entrypoint ] + args
    entrypoint = '/gsmo/pip_entrypoint.sh'


RUN_CONFIG_YML_PATH = '/run_config.yml'
if run_config:
    run_config_path = NamedTemporaryFile(delete=False)
    with open(run_config_path.name,'w') as f:
        yaml.safe_dump(dict(run_config), f)
    mounts += [ f'{run_config_path.name}:{RUN_CONFIG_YML_PATH}' ]
    args += [ '-f',RUN_CONFIG_YML_PATH ]

def get_git_id(k, fmt):
    try:
        v = line('git','config',f'user.{k}')
    except CalledProcessError:
        v = line('git','log','-n','1',f'--format={fmt}')
        stderr.write(f'Falling back to Git user {k} from most recent commit: {v}\n')
    return v

# Get Git user name/email for propagating into image
user = o(
    name  = get_git_id( 'name', '%an'),
    email = get_git_id('email', '%ae'),
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
workdir_args = [ '--workdir', workdir ]

all_args = \
    flags + \
    entrypoint_args + \
    env_args + \
    mount_args + \
    port_args + \
    user_args + \
    workdir_args + \
    group_args + \
    [image] + \
    args


def main():
    if docker:
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
                    if m['port'] != str(jupyter_dst_port):
                        raise RuntimeError(f'Jupyter running on unexpected port {m["port"]} (!= {jupyter_dst_port})')
                    token = m['token']
                    url = f'http://127.0.0.1:{jupyter_src_port}?token={token}'
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
    else:
        if not jupyter:
            raise ValueError(f'In non-docker mode, only -j/--jupyter mode is supported')
        if jupyter_src_port != jupyter_dst_port:
            raise ValueError(f'Mismatching jupyter ports in non-docker mode: {jupyter_src_port} != {jupyter_dst_port}')
        jupyter_port = jupyter_src_port
        run('jupyter','notebook','--port',jupyter_port,)


if __name__ == '__main__':
    main()
