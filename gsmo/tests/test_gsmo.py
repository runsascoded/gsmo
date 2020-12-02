from gsmo import gsmo
from utz import *


@contextmanager
def example(name, ref=None):
    repo = Repo()
    dir = join(repo.working_dir, 'example', name)
    with TemporaryDirectory() as tmpdir:
        wd = join(tmpdir, name)
        run('git','clone','--recurse-submodules',dir,wd)
        with cd(wd):
            if ref:
                run('git','reset','--hard',ref)
            yield


def run_gsmo(*args, dind=False):
    tag = env.get('GSMO_IMAGE_TAG')
    if tag:
        if dind:
            img_tag = f':dind_{tag}'
        else:
            img_tag = tag
    else:
        if dind:
            img_tag = ':dind'
        else:
            img_tag = ':'
    gsmo.main('-I','-i',img_tag,'run',*args)


def test_dind():
    with example('dind',ref='c60d0fa'):
        run_gsmo('-x','docker-hello-world.ipynb', dind=True)
        with open('nbs/docker-hello-world.ipynb','r') as f:
            import json
            nb = json.load(f)
        cells = nb['cells']
        assert len(cells) == 6
        assert cells[0]['outputs'] == []
        out = cells[-1]['outputs']
        assert all(o['name'] == 'stdout' for o in out)
        assert ''.join([ ln for o in out for ln in o['text'] ]) == '''Running: docker run --rm hello-world

Hello from Docker!
This message shows that your installation appears to be working correctly.

To generate this message, Docker took the following steps:
 1. The Docker client contacted the Docker daemon.
 2. The Docker daemon pulled the \"hello-world\" image from the Docker Hub.
    (amd64)
 3. The Docker daemon created a new container from that image which runs the
    executable that produces the output you are currently reading.
 4. The Docker daemon streamed that output to the Docker client, which sent it
    to your terminal.

To try something more ambitious, you can run an Ubuntu container with:
 $ docker run -it ubuntu bash

Share images, automate workflows, and more with a free Docker ID:
 https://hub.docker.com/

For more examples and ideas, visit:
 https://docs.docker.com/get-started/


'''


def test_hailstone():
    with example('hailstone'):
        def step(value):
            run_gsmo()
            if value == 1:
                return
            if value % 2 == 0:
                value /= 2
            else:
                value = 3*value + 1
            step(value)

        step(6)
        expected = [
            'value is already 1; exiting early',
            '2 → 1',
            '4 → 2',
            '8 → 4',
            '16 → 8',
            '5 → 16',
            '10 → 5',
            '3 → 10',
            '6 → 3',
        ]
        actual = lines('git','log',f'-n{len(expected)}','--format=%s')
        assert actual == expected


def test_factors():
    with example('factors', ref='876c95c'):
        run_gsmo()
        tree = Repo().commit().tree
        assert tree['graph.png'].hexsha == '1ed114e1dd88d516ca749e516d24ef1d28fdb0de'
        assert tree['primes.png'].hexsha == '5189952fe9bcfb9f196b55bde9f6cc119b842017'
        assert tree['ints.parquet'].hexsha == '859a019cfa004fd4bf6d93789e47c85f167a1d5d'

        run('gsmo','-I','-i','runsascoded/gsmo','run','-y','limit: 50')
        tree = Repo().commit().tree
        assert tree['graph.png'].hexsha == '6e432cd84a537648ec6559719c74e1b3021c707c'
        assert tree['primes.png'].hexsha == '107debbdfe8ae9c146d99ca97a5563201e0f8f22'
        assert tree['ints.parquet'].hexsha == '79ea92b9788a7424afc84674179db1b39c371111'

        run('gsmo','-I','-i','runsascoded/gsmo','run','-y','limit: 50')
        tree = Repo().commit().tree
        assert tree['graph.png'].hexsha == '6e432cd84a537648ec6559719c74e1b3021c707c'
        assert tree['primes.png'].hexsha == '107debbdfe8ae9c146d99ca97a5563201e0f8f22'
        assert tree['ints.parquet'].hexsha == '79ea92b9788a7424afc84674179db1b39c371111'


def get_submodule_commit(sm_path):
    parent_tree = Repo().commit().tree
    sm_hexsha = parent_tree[sm_path].hexsha
    return Repo(sm_path).commit(sm_hexsha)


def test_submodules():
    with example('submodules', ref='6e2e388'):
        run_gsmo()

        sm_commit = get_submodule_commit('generate-random-ints')
        lines = sm_commit.tree['out/ints.txt'].data_stream.read().decode().split('\n')
        assert [ int(l) for l in lines if l ] == [ 6, 34, 11, 98, 52, 34, 13, 4, 48, 68, ]

        sm_commit = get_submodule_commit('sort')
        lines = sm_commit.tree['out/ints.txt'].data_stream.read().decode().split('\n')
        assert [ int(l) for l in lines if l ] == [ 4, 6, 11, 13, 34, 48, 52, 68, 98, ]
