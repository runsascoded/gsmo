#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime as dt
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
import sys
from sys import path
path += [ str(Path(__file__).parent / 'src') ]

from cd import cd
from conf import *
from config import *
from merge_results import merge_results
from process import output, run
from src import git


now = dt.now()
now_str = now.strftime(FMT)


def get_image(config):
    image = get(config, 'docker', 'image')
    if image is None:
        base = DEFAULT_IMAGE_BASE
        version = DEFAULT_IMAGE_VERSION
    elif type(image) is object:
        base = get(image, 'base', default=DEFAULT_IMAGE_BASE)
        version = get(image, 'version', default=DEFAULT_IMAGE_VERSION)
    else:
        base = DEFAULT_IMAGE_BASE
        if type(image) is str or type(image) is float or type(image) is int:
            version = str(image)
            pieces = version.split(':', 1)
            if len(pieces) == 1:
                pass
            elif len(pieces) == 2:
                [ base, version ] = pieces
            else:
                raise Exception('Unrecognized base-image value: %s' % image)
        else:
            raise Exception('Unrecognized base-image value: %s' % image)

    return '%s:%s' % (base, version)


def build_dockerfile(config):
    lines = []
    img = get_image(config)
    lines.append('FROM %s' % img)
    if 'docker' in config:
        docker = config['docker']
        pip = strs(docker, 'pip')
        if pip:
            lines.append(' '.join([ 'RUN', 'pip3', 'install', '-U', ] + pip))
        apt = strs(docker, 'apt')
        if apt:
            lines.append(' '.join([ 'RUN', 'apt-get', 'install', '-y', ] + apt))

    dockerfile = Path(NamedTemporaryFile(prefix='Dockerfile_').name)
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
    from os.path import expanduser, expandvars
    def expand(s):
        return expandvars(expanduser(s))
    src = Path(expand(src)).absolute().resolve()
    return '%s:%s' % (src, expand(dest))


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

    docker = get(config, 'docker')

    user_args = []
    as_user = get(docker, 'as_user')
    if as_user:
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
     ] + [
        '%s:/src' % dir,
    ]

    mount_args = [ arg for mount in mounts for arg in [ '-v', clean_mount(mount) ] ]

    cmd = \
        [ 'docker', 'run' ] \
        + user_args \
        + group_args \
        + mount_args \
        + docker_args \
        + [ name, '-n', name ]

    return dockerfile, cmd


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
        msg = '%s: %s' % (now_str, status)

    state_paths = strs(config, 'state')
    out_paths = strs(config, 'out')

    files = [
        OUT_PATH,
        ERR_PATH,
        DOCKERFILE_PATH,
        success_path,
        failure_path,
    ] \
    + state_paths \
    + out_paths

    git.add(files)

    name = get_name(config)
    git.set_user_configs(name)

    # "-q" is necessary when committing files >1GB; https://public-inbox.org/git/xmqqsha3o4u7.fsf@gitster-ct.c.googlers.com/t/
    run([ 'git', 'commit', '-a', '-q', '--allow-empty', '-m', msg ])
    run_sha = git.sha()
    print('Committed run: %s' % run_sha)

    return run_sha, msg


def run_module(
    module,
    preserve_tmp_clones=False,
    capture_output=True,
):
    module = Path(module).absolute().resolve()
    runs_path = get_runs_clone(module)

    if capture_output:
        runner_logs_dir = runs_path / LOGS_DIR / RUNNER_LOGS_DIR / now_str
        runner_logs_dir.mkdir(parents=True)
        stdout_path = runner_logs_dir / RUNNER_STDOUT_BASENAME
        stderr_path = runner_logs_dir / RUNNER_STDERR_BASENAME

        print('Redirecting stdout/stderr to %s, %s' % (stdout_path, stderr_path))
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = stdout_path.open('w')
        sys.stderr = stderr_path.open('w')

    try:
        dir = TemporaryDirectory(prefix='gismo_')

        if preserve_tmp_clones:
            from contextlib import nullcontext
            ctx = nullcontext()
        else:
            ctx = dir

        with ctx:
            dir = Path(dir.name)

            with cd(module):

                config = load_config()
                name = get_name(config)
                dockerfile_src, cmd = make_cmd(config, dir)
                run([ 'git', 'clone', module, dir ])

                dockerfile = dir / DOCKERFILE_PATH
                print('Installing Dockerfile %s in temporary clone: %s' % (dockerfile_src, dockerfile))
                dockerfile_src.rename(dockerfile)

                git.set_user_configs(name)

                with cd(dir):
                    run([ 'docker', 'build', '-t', name, '-f', dockerfile, '.' ])
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
    finally:
        if capture_output:
            print('Restoring stdout, stderr')
            sys.stdout.close()
            sys.stderr.close()
            sys.stdout = original_stdout
            sys.stderr = original_stderr


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--preserve_tmp_clones', '-p', default=False, action='store_true', help="When true, don't clean up the temporary clones of modules that are run (useful for debugging)")
    parser.add_argument('--pipe_output', '-o', default=False, action='store_true', help="When true, pipe runner stdout/stderr through to the current terminal (by default, they're logged under runs/logs/runner")
    parser.add_argument('modules', nargs='*', help='Path to module to run')
    args, docker_args = parser.parse_known_args()

    modules = args.modules
    if not modules:
        modules = [ Path.cwd() ]

    preserve_tmp_clones = args.preserve_tmp_clones
    pipe_output = args.pipe_output

    for module in modules:
        run_module(module, preserve_tmp_clones=preserve_tmp_clones, capture_output=not pipe_output)
