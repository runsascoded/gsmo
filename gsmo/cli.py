from os import listdir
from os.path import isdir
from re import match
import yaml


class Arg:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


run_args = [
    Arg('-b','--branch',help="Branch to clone, work in, and push results back to. Can also be passed as a trailing '@<branch>' slug on directory path or remote Git repo URL. For local repositories, implies --clone"),
    Arg('--clone',action='store_true',help='Clone local directory into a temporary dir for duration of the run'),
    Arg('--commit',action='append',help='Paths to `git add` and commit after running'),
    Arg('-C','--dir',help="Resolve paths (incl. mounts) relative to this directory (default: current directory)"),
    Arg('-o','--out',help='Path or directory to write output notebook to (relative to `--dir` directory; default: "nbs")'),
    Arg('--push',action='append',help='Push to this remote spec when done running'),
    Arg('-x','--run','--execute',help='Notebook to run (default: run.ipynb)'),
    Arg('-y','--yaml',action='append',help='YAML string(s) with configuration settings for the module being run'),
    Arg('-Y','--yaml-path',action='append',help='YAML file(s) with configuration settings for the module being run'),  # TODO: update example nb
]


class Idem(type):
    def __call__(cls, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], Spec):
            print(f'found spec: {args[0]}')
            return args[0]
        self = cls.__new__(cls, *args, **kwargs)
        self.__init__(*args, **kwargs)
        return self

    def __init__(cls, name, bases, attributes):
        super().__init__(name, bases, attributes)


class Spec(metaclass=Idem):
    SPEC_REGEX = '(?P<src>[^:]*)(?::(?P<dst>.*))?'
    FULL_REGEX = f'(?P<remote>[^/]+)(?:/{SPEC_REGEX})?'

    def _parse_spec(self, spec, full):
        if spec is None:
            (self.src, self.dst) = (None, None)
            if full:
                self.remote = None
            return
        if full:
            regex = self.FULL_REGEX
        else:
            regex = self.SPEC_REGEX
        if not (m := match(regex, spec)):
            raise ValueError(f'Invalid spec: {spec}')
        if full:
            self.remote = m['remote']
        self.src = m['src'] or None  # '' ⟶ None
        if m['dst'] is None:
            self.dst = self.src
        else:
            self.dst = m['dst'] or None  # '' ⟶ None

    def __init__(self, *args):
        if not args:
            self.remote = None
            self.src = None
            self.dst = None
        else:
            (arg, *args) = args
            if not args:
                if arg is None:
                    self.remote = None
                    self.src = None
                    self.dst = None
                else:
                    self._parse_spec(arg, full=True)
            else:
                (self.remote, arg, *args) = (arg, *args)
                if not args:
                    self._parse_spec(arg, full=False)
                else:
                    (self.src, self.dst) = (arg, *args)
            if self.remote is None and (self.src is not None or self.dst is not None):
                raise ValueError(f'Invalid spec: (src || dst) ⟹ remote. ({self.remote=}, {self.src=}, {self.dst=})')

    def __str__(self):
        tpl = tuple(self)
        if len(tpl) == 2:
            return f'{tpl[0]}/{tpl[1]}'
        elif len(tpl) == 1:
            (remote,) = tpl
            return remote
        else:
            return ''

    def __repr__(self): return str(self)

    def __iter__(self):
        if self.remote:
            yield self.remote
            if self.src or self.dst:
                if self.src == self.dst:
                    yield self.src
                else:
                    yield f'{self.src or ""}:{self.dst or ""}'


REMOTE_REFSPEC_REGEX = '(?P<remote>[^/]+)(?:/(?P<spec>.*))?'
def parse_ref(ref):
    if not (m := match(REMOTE_REFSPEC_REGEX, ref)):
        raise ValueError(f'Invalid push ref: {ref}')
    remote = m['remote']
    spec = m['spec']
    if spec:
        return (remote, spec)
    else:
        return (remote,)


def load_run_config(args):
    # Load configs to pass into run container
    run_config = {}
    if (run_config_yaml_paths := args.yaml_path):
        for run_config_yaml_path in run_config_yaml_paths:
            if isdir(run_config_yaml_path):
                raise RuntimeError(f'run_config_yaml_path {run_config_yaml_path} is a directory: {listdir(run_config_yaml_path)}')
            with open(run_config_yaml_path,'r') as f:
                run_config.update(yaml.safe_load(f))

    if (run_config_yaml_strs := args.yaml):
        for run_config_yaml_str in run_config_yaml_strs:
            run_config_yaml = yaml.safe_load(run_config_yaml_str)
            run_config.update(run_config_yaml)

    return run_config
