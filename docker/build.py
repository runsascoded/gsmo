#!/usr/bin/env python

from utz import *

def build(repository, file, latest, python_version, push, tokens, usernames, tag_prefix=None, **build_args):
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
    run(
        'docker','build',
        '-t',base_repo,
        '-f',file,
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
            tag(sha, python_version)
            for t in lines('git','tag','--points-at','HEAD'):
                tag(t)
                tag(t, python_version)
        else:
            print("Detected uncommitted changes; skipping Git SHA tag")

def main():
    parser = ArgumentParser()
    parser.add_argument('-l','--latest',action='store_true',help='When set, only create "latest" tag. By default, a tag for the python version is also created, as well as for the current Git commit (if there are no uncommitted changes)')
    parser.add_argument('-p','--python-version',default='3.8.6',help='Python version to build base image against')
    parser.add_argument('-P','--push',action='store_true',help='When set, push image')
    parser.add_argument('-t','--token',nargs='*',help='Token to log in to Docker Hub with (or multiple arguments of the form "<repository>=<token>")')
    parser.add_argument('-u','--username',nargs='*',help='User to log in to Docker Hub as (or multiple arguments of the form "<repository>=<username>")')
    parser.add_argument('--repository',default='runsascoded/gsmo',help='Docker repository for built image')
    args = parser.parse_args()
    latest = args.latest
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

    chdir(dirname(__file__))

    if not check('git','diff','--quiet','--exit-code','HEAD'):
        raise ValueError("Refusing to build from unclean git worktree")

    # Require a branch or tag to clone for shallow /gsmo checkout inside container
    ref = line('git','symbolic-ref','-q','--short','HEAD', empty_ok=True)
    if not ref:
        tags = lines('git','tag','--points-at','HEAD')
        if not tags:
            raise ValueError(f"Couldn't infer current branch or tag for self-clone of gsmo into Docker image")
        ref = tags[0]

    build(
        repository=repository,
        file='Dockerfile',
        latest=latest,
        python_version=python_version,
        push=push,
        tokens=tokens,
        usernames=usernames,
        REF=ref,
    )
    build(
        repository=repository,
        file='Dockerfile.dind',
        tag_prefix='dind',
        latest=latest,
        python_version=python_version,
        push=push,
        tokens=tokens,
        usernames=usernames,
    )

if __name__ == '__main__':
    main()
