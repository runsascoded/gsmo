#!/usr/bin/env python3

from argparse import ArgumentParser
from configparser import ConfigParser
from pathlib import Path
from tempfile import TemporaryDirectory
from sys import path
path += [ str(Path(__file__).parent / 'src') ]

from cd import cd
from conf import *
from config import *
from src import git
from merge_results import merge_results
from process import output, run


def write_git_config(config):
    name = get_name(config)
    if 'git' in config:
        git = config['git']
    else:
        git = {
            'user': {
                'name': name,
                'email': '%s@%s' % (name, name)
            }
        }
    config = ConfigParser()
    for name, section in git.items():
        config[name] = {}
        for k,v in section.items():
            config[name][k] = v

    conf_dir = Path('conf')
    conf_dir.mkdir(exist_ok=True)
    git_config_path = conf_dir / '.gitconfig'
    with git_config_path.open('w') as f:
        config.write(f)

    return git_config_path


def build_dockerfile(config):
    git_config_path = write_git_config(config)
    lines = []
    lines.append('FROM cron:latest')
    if 'docker' in config:
        docker = config['docker']
        pip = strs(docker, 'pip')
        if pip:
            lines.append(' '.join([ 'RUN', 'pip3', 'install', '-U', ] + pip))
        apt = strs(docker, 'apt')
        if apt:
            lines.append(' '.join([ 'RUN', 'apt-get', 'install', '-y', ] + apt))

    lines.append('ADD %s /.gitconfig' % git_config_path)
    dockerfile = Path('Dockerfile')
    with dockerfile.open('w') as f:
        f.write('\n'.join(lines + ['']))

    return dockerfile


def clean_mount(mount):
    pieces = mount.split(':')
    if len(pieces) == 1:
        src = pieces[0]
        dest = '/%s' % Path(src).name
        pieces = [ src, dest ]

    if len(pieces) != 2:
        raise Exception('Invalid mount spec: %s' % mount)

    [ src, dest ] = pieces
    src = Path(src).absolute().resolve()
    return '%s:%s' % (src, dest)


def clean_group(group):
    if group.index('/') >= 0:
        return output([ 'stat', '-c', '%g', group ]).strip()
    else:
        return output([ 'id', '-g', group ]).strip()


def load_config():
    import yaml
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open('r') as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    return config


def make_cmd(config, dir):
    name = get_name(config)
    dockerfile = build_dockerfile(config)

    run([ 'docker', 'build', '-t', name, '-f', dockerfile, '.' ])

    docker = get(config, 'docker')

    user_args = []
    if get(docker, 'as_user'):
        uid = int(output([ 'id', '-u' ]).strip())
        gid = int(output([ 'id', '-g' ]).strip())
        user_args = [ '-u', '%d:%d' % (uid, gid) ]

    groups = strs(docker, 'add_groups')
    group_args = [ arg for group in groups for arg in [ '--group-add', clean_group(group) ] ]

    mount = strs(docker, 'mount')
    mounts = strs(docker, 'mounts')

    if mount and mounts:
        raise Exception('Found "docker.mount" and "docker.mounts" keys: (%s, %s)' % (mount, mounts))

    if mount:
        mounts = mount

    mounts = [
         mount
         for mount in mounts
     ] + [ '%s:/src' % dir ]

    mount_args = [ arg for mount in mounts for arg in [ '-v', clean_mount(mount) ] ]

    cmd = \
        [ 'docker', 'run' ] \
        + user_args \
        + group_args \
        + mount_args \
        + docker_args \
        + [ name, '-n', name ]

    return cmd


def get_runs_clone(module):
    runs_path = module / RUNS_DIR
    runs_path = runs_path.absolute().resolve()

    if not runs_path.exists():
        # Initialize fresh runs/ dir from current state of repo
        run([ 'git', 'clone', module, runs_path])

    return runs_path


def make_run_commit(config):
    success_path = Path(SUCCESS_PATH)
    failure_path = Path(FAILURE_PATH)
    if success_path.exists():
        if failure_path.exists():
            raise Exception('Found %s and %s' % (success_path, failure_path))
        status = 'succeeded'
    elif failure_path.exists():
        status = 'failed'
    else:
        raise Exception('Found neither %s nor %s' % (success_path, failure_path))

    if MSG_PATH.exists():
        with MSG_PATH.open('r') as f:
            msg = f.read()
        MSG_PATH.unlink()
    else:
        from datetime import datetime as dt
        now = dt.now()
        now_str = now.strftime(FMT)

        msg = '%s: %s' % (now_str, status)

    state_paths = strs(config, 'state')
    out_paths = strs(config, 'out')

    files = [
        OUT_PATH,
        ERR_PATH,
        success_path,
        failure_path,
    ] \
    + state_paths \
    + out_paths

    git.add(files)

    # "-q" is necessary when committing files >1GB; https://public-inbox.org/git/xmqqsha3o4u7.fsf@gitster-ct.c.googlers.com/t/
    run([ 'git', 'commit', '-a', '-q', '--allow-empty', '-m', msg ])
    run_sha = git.sha()
    print('Committed run: %s' % run_sha)

    return run_sha, msg


def run_module(module):
    module = Path(module).absolute().resolve()

    with cd(module):

        config = load_config()
        runs_path = get_runs_clone(module)

        # from contextlib import nullcontext
        # dir = TemporaryDirectory(prefix='gismo_')
        # with nullcontext():
        #     dir = Path(dir.name)
        with TemporaryDirectory(prefix='gismo_') as dir:
            dir = Path(dir)
            cmd = make_cmd(config, dir)
            run([ 'git', 'clone', module, dir ])
            with cd(dir):

                remote = git.remote()

                # if not upstream_branch:
                upstream_branch = DEFAULT_UPSTREAM_BRANCH
                upstream_remote_branch = '%s/%s' % (remote, upstream_branch)

                original_upstream_sha = git.sha(upstream_remote_branch)
                print('Working from upstream branch %s (%s)' % (upstream_remote_branch, original_upstream_sha))

                base_sha = git.sha()
                if original_upstream_sha != base_sha:
                    print('Overriding cloned HEAD %s to start from upstream %s (%s)' % (base_sha, upstream_remote_branch, original_upstream_sha))
                    git.checkout(upstream_remote_branch)
                    base_sha = original_upstream_sha

                run(cmd)

                run_sha, msg = make_run_commit(config)

                merge_results(
                    module,
                    runs_path,
                    config,
                    base_sha,
                    run_sha,
                    msg,
                    original_upstream_sha,
                    remote,
                    upstream_branch,
                )


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('modules', nargs='*', default=None, help='Path to module to run')
    args, docker_args = parser.parse_known_args()

    modules = args.modules
    if modules is None:
        modules = [ Path.cwd() ]

    for module in modules:
        run_module(module)
