#!/usr/bin/env python

from utz import *

def build(repository, file, latest, python_version, push):
    run(
        'docker','build',
        '-t',repository,
        '-f',file,
        '--build-arg',f'PYTHON={python_version}',
        '.',
    )

    def tag(t):
        img = f'{repository}:{t}'
        if not latest:
            run('docker','tag',repository,img)
        if push:
            run('docker','push',img)

    if not latest:
        tag(python_version)
        if check('git','diff','--quiet','--exit-code','HEAD'):
            sha = line('git','log','-n1','--format=%h')
            tag(f'{sha}_{python_version}')
        else:
            print("Detected uncommitted changes; skipping Git SHA tag")

def main():
    parser = ArgumentParser()
    parser.add_argument('--latest',action='store_true',help='When set, only create "latest" tag. By default, a tag for the python version is also created, as well as for the current Git commit (if there are no uncommitted changes)')
    parser.add_argument('-p','--python-version',default='3.8.6',help='Python version to build base image against')
    parser.add_argument('-P','--push',action='store_true',help='When set, push image')
    parser.add_argument('--repository',default='runsascoded/gsmo',help='Docker repository for built image')
    args = parser.parse_args()
    latest = args.latest
    python_version = args.python_version
    push = args.push
    repository = args.repository

    chdir(dirname(__file__))
    build(
        repository=repository,
        file='Dockerfile',
        latest=latest,
        python_version=python_version,
        push=push,
    )
    build(
        repository=f'{repository}/dind',
        file='Dockerfile.dind',
        latest=latest,
        python_version=python_version,
        push=push,
    )

if __name__ == '__main__':
    main()
