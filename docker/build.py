#!/usr/bin/env python

from utz import *

VERSION_TAG_RGX = r'^v(?P<version>\d+\.\d+\.\d+)$'
GSMO_DIR = '/gsmo'
GH_REPO = 'runsascoded/gsmo'

def build(
    repository: str,
    latest: bool,
    python_version: str,
    push: bool,
    tokens: dict,
    usernames: dict,
    dockerfile: str = None,
    tag_prefix: str = None,
    embed: str = None,
    ref: str = None,
    sha: str = None,
    docker_dir: str = None,
    **build_args,
):
    def build_repo(*pcs):
        if tag_prefix:
            pcs = (tag_prefix,) + pcs
        tg = '_'.join(pcs)
        if tg:
            return f'{repository}:{tg}'
        else:
            return repository

    def _push(tagged_repo):
        if push:
            if tokens:
                token = tokens.get(repository, tokens.get(None))
                if token:
                    cmd = ['docker','login','-p',token]
                    if username := usernames.get(repository, usernames.get(None)):
                        cmd += ['-u',username]

                    run(cmd)
            run('docker','push',tagged_repo)

    base_repo = build_repo()
    if embed:
        from utz import docker
        from utz.use import use
        file = docker.File(copy_dir=docker_dir)
        with use(file):
            NOTE('Base Dockerfile for Python projects; recent Git, pandas/jupyter/sqlalchemy, and dotfiles for working in-container')
            FROM('python',f'{python_version}-slim')
            LN()
            NOTE('Disable pip upgrade warning, add default system-level gitignore, and configs for setting git user.{email,name} at run-time',)
            COPY(
                'etc/pip.conf','etc/.gitignore','etc/gitconfig',
                '/etc/',
            )
            LN()
            RUN(
                'echo "deb http://ftp.us.debian.org/debian testing main" >> /etc/apt/sources.list',
                'apt-get update',
                'apt-get install -y -o APT::Immediate-Configure=0 curl gcc g++ git nano',
                'apt-get clean all',
                'rm -rf /var/lib/apt/lists',
            )
            LN()
            pips = [
                dict(
                    pip=None,
                    wheel=None,
                ),
                dict(
                    jupyter='1.0.0',
                    nbdime='2.1.0',
                    pandas='1.1.3',
                    papermill='2.2.0',
                    pyyaml='5.3.1',
                )
            ]
            NOTE('Basic pip dependencies: Jupyter, pandas')
            RUN(*[
                'pip install --upgrade --no-cache %s' % ' '.join([
                    f'{k}=={v}' if v else k
                    for k,v in pip.items()
                ])
                for pip in pips
            ])
            LN()
            NOTE('Install dotfiles + bash helpers and Jupyter configs')
            WORKDIR('/root')
            RUN(
                'curl -L https://j.mp/_rc > _rc',
                'chmod u+x _rc',
                './_rc -b server runsascoded/.rc',
            )
            COPY('usr/local/etc/jupyter/nbconfig/notebook.json','/usr/local/etc/jupyter/nbconfig/'); LN()

            WORKDIR(); LN()

            NOTE("Create an open directory for pointing anonymouse users' $HOME at (e.g. `-e HOME=/home -u `id -u`:`id -g` `)")
            RUN('chmod ugo+rwx /home')

            NOTE('Simple .bashrc for anonymous users that just sources /root/.bashrc')
            COPY('home/.bashrc','/home/.bashrc')
            NOTE('Make sure /root/.bashrc is world-accessible')
            RUN('chmod o+rx /root')
            LN()
            RUN('pip install --upgrade --no-cache utz[setup]==0.0.27')
            LN()
            ENTRYPOINT([ "gsmo-entrypoint", "/src" ])
            if embed == 'clone':
                assert ref
                assert sha
                RUN(
                    f'git clone -b {ref} --depth 1 https://github.com/{GH_REPO} {GSMO_DIR}',
                    f'cd {GSMO_DIR}',
                    f'git checkout {sha}',
                )
            elif embed == 'copy':
                COPY('.',GSMO_DIR, dir=None)
            else:
                raise ValueError('Invalid "embed" value: %s; choices: {clone,copy}' % embed)
            RUN(f'pip install -e {GSMO_DIR}')

        file.build(base_repo)
    else:
        run(
            'docker','build',
            '-t',base_repo,
            '-f',dockerfile,
            [ ['--build-arg',f'{k}={v}'] for k,v in build_args.items() ],
            '.',
        )

    _push(base_repo)

    def tag(*tag_pcs):
        repo = build_repo(*tag_pcs)
        if not latest:
            run('docker','tag',base_repo,repo)
            _push(repo)

    if not latest:
        tag(python_version)
        if check('git','diff','--quiet','--exit-code','HEAD'):
            sha = line('git','log','-n1','--format=%h')
            tag(sha)
            tag(sha, python_version)
            for t in lines('git','tag','--points-at','HEAD'):
                if (m := match(VERSION_TAG_RGX, t)):
                    t = m['version']
                tag(t)
                tag(t, python_version)
        else:
            print("Detected uncommitted changes; skipping Git SHA tag")

def main():
    parser = ArgumentParser()
    parser.add_argument('-c','--copy',action='store_true',help='Copy current gsmo Git clone into Docker image (instead of cloning from GitHub)')
    parser.add_argument('-D','--no-dind',action='store_true',help='Skip building docker-in-docker (DinD) images')
    parser.add_argument('-l','--latest',action='store_true',help='Only create "latest" tag. By default, a tag for the python version is also created, as well as for the current Git commit (if there are no uncommitted changes)')
    parser.add_argument('-p','--python-version',default='3.8.6',help='Python version to build base image against')
    parser.add_argument('-P','--push',action='store_true',help='Push built images')
    parser.add_argument('-t','--token',nargs='*',help='Token to log in to Docker Hub with (or multiple arguments of the form "<repository>=<token>")')
    parser.add_argument('-u','--username',nargs='*',help='User to log in to Docker Hub as (or multiple arguments of the form "<repository>=<username>")')
    parser.add_argument('--repository',default='runsascoded/gsmo',help='Docker repository for built image')
    args = parser.parse_args()
    copy = args.copy
    latest = args.latest
    dind = not args.no_dind
    python_version = args.python_version
    push = args.push
    repository = args.repository
    def parse_dict(attr):
        arg = getattr(args, attr)
        ret = {}
        if isinstance(arg, list):
            for entry in arg:
                pcs = entry.split('=', 1)
                if len(pcs) == 2:
                    [ repository, arg ] = pcs
                    ret[repository] = arg
                elif len(pcs) == 1:
                    if None in ret:
                        raise ValueError(f'Invalid --{attr}: multiple default values ({ret[None]}, {pcs[0]})')
                    ret[None] = arg
                else:
                    raise ValueError(f'Invalid --{attr}: {arg}')
        return ret

    tokens = parse_dict('token')
    usernames = parse_dict('username')

    docker_dir = dirname(__file__)
    chdir(docker_dir)

    build_kwargs = dict(
        repository=repository,
        latest=latest,
        python_version=python_version,
        push=push,
        tokens=tokens,
        usernames=usernames,
    )
    if copy:
        git_root = line('git','rev-parse','--show-toplevel')
        with cd(git_root):
            build(
                **build_kwargs,
                docker_dir=docker_dir,
                embed='copy',
            )
    else:
        if not check('git','diff','--quiet','--exit-code','HEAD'):
            raise ValueError("Refusing to build from unclean git worktree")

        # Require a branch or tag to clone for shallow /gsmo checkout inside container
        ref = line('git','symbolic-ref','-q','--short','HEAD', err_ok=True)
        if not ref:
            tags = lines('git','tag','--points-at','HEAD')
            if not tags:
                raise ValueError(f"Couldn't infer current branch or tag for self-clone of gsmo into Docker image")
            ref = tags[0]

        sha=line('git','log','-n','1','--format=%h')

        build(
            **build_kwargs,
            dockerfile='Dockerfile',
            embed='clone',
            ref=ref,
            sha=sha,
        )

    if dind:
        build(
            **build_kwargs,
            dockerfile='Dockerfile.dind',
            tag_prefix='dind',
        )

if __name__ == '__main__':
    main()
