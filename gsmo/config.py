
from os.path import basename, exists, isfile, join, sep
from pathlib import Path
from sys import stderr
from utz.collections import singleton
from utz import o
from utz.process import line


DEFAULT_CONFIG_STEMS = ['gsmo','config']
CONFIG_XTNS = ['yaml','yml']
DEFAULT_SRC_MOUNT_DIR = '/src'
DEFAULT_RUN_NB = 'run.ipynb'
DEFAULT_NB_DIR = 'nbs'

class Config:
    def __init__(self, args):
        self.args = args
        config_paths = [
            f
            for stem in DEFAULT_CONFIG_STEMS
            for xtn in CONFIG_XTNS
            if exists(f := f'{stem}.{xtn}')
        ]

        if config_paths:
            config_path = singleton(config_paths)
            import yaml
            with open(config_path,'r') as f:
                config = o(yaml.safe_load(f))
        else:
            config = o()

        self.config = config

    def get(self, keys, default=None):
        if isinstance(keys, str):
            keys = [keys]

        for k in keys:
            if hasattr(self.args, k):
                if (v := getattr(self.args, k)) is not None:
                    return v

        for k in keys:
            if k in self.config:
                print(f'Found config {k}')
                return self.config[k]

        return default


def lists(args, sep=','):
    if args is None:
        return []

    if isinstance(args, str):
        args = args.split(sep)

    return args


def strs(config, *keys):
    config = get(config, *keys)
    if config:
        if isinstance(config, list):
            return config
        else:
            return [ config ]
    return []


def get(config, *keys, default=None):
    keys = list(keys)
    if keys:
        key = keys.pop(0)
        if not config or not key in config:
            return default
        return get(config[key], *keys)

    return config


def get_name(config):
    if 'name' in config:
        return config['name']
    return Path.cwd().name


def clean_mount(mount, missing_mount='raise'):
    pieces = mount.split(':')
    if len(pieces) == 1:
        src = pieces[0]
        dst = '/%s' % src
        pieces = [ src, dst ]

    if len(pieces) != 2:
        raise Exception('Invalid mount spec: %s' % mount)

    [ src, dst ] = pieces
    from os.path import abspath, expanduser, expandvars, realpath
    def expand(path): return expandvars(expanduser(path))
    src = realpath(abspath(expand(src)))
    dst = expand(dst)
    if isfile(src) and dst.endswith(sep):
        dst = join(dst, basename(src))
    if not exists(src):
        msg = f"Mount src doesn't exist: {src}"
        if missing_mount in ['raise','err','error']:
            raise ValueError(msg)
        if missing_mount == 'warn':
            stderr.write('%s\n' % msg)
        else:
            assert missing_mount in ('ignore','ok')
        return None
    return '%s:%s' % (src, dst)


def clean_group(group):
    if exists(group):
        return line('stat','-c','%g',group)
    else:
        return line('id','-g',group)
