from gsmo import execute
from utz import cd, sh


class Modules:
    def __init__(self, run=None, skip=None, conf=None):
        if isinstance(run, str): run = run.split(',')
        if isinstance(skip, str): skip = skip.split(',')
        if run is not None and skip is not None:
            raise RuntimeError('Specify at most one of {run,skip}: (%s, %s)' % (run, skip))
        self.runs = run
        self.skips = skip
        self.conf = conf

    def run(self, module, nb='run.ipynb', out='nbs', *args, **kwargs):
        if self.skips and module in self.skips:
            print(f'Module {module} marked as "skip"; skipping')
            return
        if self.runs and module not in self.runs:
            print(f'Module {module} not marked as "run"; skipping')
            return

        module_kwargs = self.conf.get('module', {})
        module_kwargs.update(kwargs)

        with cd(module):
            execute(
                nb,
                out=out,
                *args,
                **module_kwargs,
            )
        sh('git','add',module)
        sh('git','commit','-m',module)

    def __call__(self, *args, **kwargs): return self.run(*args, **kwargs)
