
from git import Repo
from utz.imports import *


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

def test_hailstone():
    with example('hailstone'):
        def step(value):
            run('gsmo','-I','run',)
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
    with example('factors', ref='94a8c5c'):
        run('gsmo','-I','-i','runsascoded/gsmo','run',)
        tree = Repo().commit().tree
        # assert tree.hexsha == 'cd94100b5af964ee34ec469ecbf992e4e1fb7a76'
        assert tree['graph.png'].hexsha == '1ed114e1dd88d516ca749e516d24ef1d28fdb0de'
        assert tree['primes.png'].hexsha == '5189952fe9bcfb9f196b55bde9f6cc119b842017'
        assert tree['ints.parquet'].hexsha == ''
