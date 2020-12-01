#!/usr/bin/env python

from utz import *

from ..config import IMAGE_HOME

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
    embed: str = None,
    ref: str = None,
    sha: str = None,
    docker_dir: str = None,
    dind: bool = False,
    refs: List[str] = None,
):
    if dind:
        tag_prefix = 'dind'
    else:
        tag_prefix = None

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
        RUN('chmod o+rx /etc/pip.conf /etc/.gitignore /etc/gitconfig')
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
        COPY('usr/local/etc/jupyter/nbconfig/notebook.json','/usr/local/etc/jupyter/nbconfig/')
        RUN('chmod o+rx /usr/local/etc/jupyter/nbconfig/ /root')
        LN()

        WORKDIR(); LN()

        NOTE("Create a $HOME dir (independent of user name; sometimes user is anonymous, e.g. via `-u $(id -u):$(id -g)`)")
        ENV(HOME=IMAGE_HOME)
        RUN(f'chmod ugo+rwx {IMAGE_HOME}')

        NOTE('Simple .bashrc for anonymous users that just sources /root/.bashrc')
        COPY('home/.bashrc',f'{IMAGE_HOME}/.bashrc')
        LN()
        RUN('pip install --upgrade --no-cache utz[setup]==0.1.0')
        LN()
        ENTRYPOINT([ "gsmo-entrypoint", "/src" ])

        if dind:
            RUN(
                'apt-get update',
                'apt-get install -y apt-transport-https ca-certificates gnupg2 software-properties-common sudo',
                'curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -',
                'add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian buster stable"',
                'apt-get update',
                'apt-get install -y docker-ce docker-ce-cli containerd.io',
                'apt-get clean all',
                'rm -rf /var/lib/apt/lists',
            )

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
            WORKDIR(GSMO_DIR)
            RUN(
                'git clean -fdx',
                f'chmod -R go+rx {GSMO_DIR}',
            )
            WORKDIR()
        else:
            raise ValueError('Invalid "embed" value: %s; choices: {clone,copy}' % embed)

        RUN(f'pip install -e {GSMO_DIR}')

        file.build(base_repo)

    _push(base_repo)

    def tag(*tag_pcs):
        repo = build_repo(*tag_pcs)
        if not latest:
            run('docker','tag',base_repo,repo)
            _push(repo)

    if not latest:
        tag(python_version)
        if refs is not None:
            for r in refs:
                tag(r)
                tag(r, python_version)
        else:
            if not lines('git','status','--short','--untracked-files','no'):
                sha = line('git','log','-n1','--format=%h')
                tag(sha)
                tag(sha, python_version)
                for t in lines('git','tag','--points-at','HEAD'):
                    if (m := match(VERSION_TAG_RGX, t)):
                        t = m['version']
                    tag(t)
                    tag(t, python_version)

                full_sha = line('git','log','-n1','--format=%H')
                tag(full_sha)
                tag(full_sha, python_version)
                branch_lines = lines('git','show-ref','--heads', err_ok=True) or []
                for ln in branch_lines:
                    [branch_sha, branch_ref] = ln.split(' ', 2)
                    if branch_sha == full_sha:
                        if (m := match('^refs/heads/(?P<branch>.*)', branch_ref)):
                            branch = m['branch']
                            tag(branch)
                            tag(branch, python_version)
            else:
                print("Detected uncommitted changes; skipping Git SHA tag")

def main():
    parser = ArgumentParser()
    parser.add_argument('-c','--copy',action='store_true',help='Copy current gsmo Git clone into Docker image (instead of cloning from GitHub)')
    parser.add_argument('-D','--no-dind',action='store_true',help='Skip building docker-in-docker (DinD) images')
    parser.add_argument('-l','--latest',action='store_true',help='Only create "latest" tag. By default, a tag for the python version is also created, as well as for the current Git commit (if there are no uncommitted changes)')
    parser.add_argument('-p','--python-version',default='3.8.6',help='Python version to build base image against')
    parser.add_argument('-P','--push',action='store_true',help='Push built images')
    parser.add_argument('-r','--ref',action='append',help='Ref-name(s) to include as tags of the built image (default: current tags and branches)')
    parser.add_argument('-t','--token',action='append',help='Token to log in to Docker Hub with (or multiple arguments of the form "<repository>=<token>")')
    parser.add_argument('-u','--username',action='append',help='User to log in to Docker Hub as (or multiple arguments of the form "<repository>=<username>")')
    parser.add_argument('--repository',default='runsascoded/gsmo',help='Docker repository for built image')
    args = parser.parse_args()
    copy = args.copy
    latest = args.latest
    dind = not args.no_dind
    python_version = args.python_version
    push = args.push
    refs = args.ref
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

    docker_dir='docker'
    chdir(docker_dir)

    if copy:
        embed = 'copy'
    else:
        embed = 'clone'

    build_kwargs = dict(
        repository=repository,
        latest=latest,
        python_version=python_version,
        push=push,
        tokens=tokens,
        usernames=usernames,
        embed=embed,
        refs=refs,
    )

    def build_img(dind):
        kwargs = dict(dind=dind, **build_kwargs)
        if copy:
            git_root = line('git','rev-parse','--show-toplevel')
            with cd(git_root):
                build(
                    **kwargs,
                    docker_dir=docker_dir,
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
                **kwargs,
                ref=ref,
                sha=sha,
            )

    build_img(dind=False)
    if dind:
        build_img(dind=True)


if __name__ == '__main__':
    main()
