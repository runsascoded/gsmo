
from utz import *

def test_hailstone():
    repo = Repo()
    hailstone_dir = join(repo.working_dir, 'example', 'hailstone')
    with TemporaryDirectory() as dir:
        run('git','clone',hailstone_dir,dir)
        with cd(dir):
            def step(value):
                run('gsmo','-I')
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
