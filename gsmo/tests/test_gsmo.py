
from utz import *


@contextmanager
def example(name, ref=None):
    repo = Repo()
    dir = join(repo.working_dir, 'example', name)
    with TemporaryDirectory() as wd:
        run('git','clone',dir,wd)
        with cd(wd):
            if ref:
                run('git','reset','--hard',ref)
            yield

args = ['-I']
if 'GSMO_IMAGE' in env:
    args += ['-i',env['GSMO_IMAGE']]


def test_hailstone():
    with example('hailstone'):
        def step(value):
            run('gsmo',*args,'run',)
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
        run('gsmo',*args,'run',)
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
