from .papermill import execute
from . import gsmo

from utz import cd, env, getcwd, git, NamedTemporaryFile, relpath, stdout


class Modules:
    def __init__(self, run=None, skip=None, conf=None):
        if isinstance(run, str): run = run.split(',')
        if isinstance(skip, str): skip = skip.split(',')
        if run is not None and skip is not None:
            raise RuntimeError('Specify at most one of {run,skip}: (%s, %s)' % (run, skip))
        self.runs = run
        self.skips = skip
        self.conf = conf or {}

    def run(self, module, nb='run.ipynb', out='nbs', dind=None, *args, **kwargs):
        if self.skips and module in self.skips:
            print(f'Module {module} marked as "skip"; skipping')
            return
        if self.runs and module not in self.runs:
            print(f'Module {module} not marked as "run"; skipping')
            return

        module_kwargs = self.conf.get(module) or {}
        module_kwargs.update(kwargs)

        cwd = getcwd()
        with git.txn(add=module, msg=module):
            with cd(module):
                ctx = relpath(cwd)
                print(f'Running module: {module} ({ctx=})')
                if dind is not False:
                    with NamedTemporaryFile() as tmp:
                        with open(tmp.name,'w') as f:
                            import yaml
                            yaml.safe_dump(module_kwargs, f, sort_keys=False)
                        print(f'Wrote run config to {tmp.name}:\n')
                        yaml.safe_dump(module_kwargs, stdout, sort_keys=False)
                        print('')
                        cmd = []
                        if 'GSMO_IMAGE' in env:
                            cmd += ['-i',env['GSMO_IMAGE']]
                        cmd += ['-I','--ctx',ctx,'run','-o',out,'-x',nb,'-Y',tmp.name]
                        gsmo.main(*cmd)
                else:
                    execute(
                        nb,
                        out,
                        *args,
                        **module_kwargs,
                    )

    def __call__(self, *args, **kwargs): return self.run(*args, **kwargs)
