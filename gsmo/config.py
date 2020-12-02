
from os.path import basename, exists, isfile, join, sep
from pathlib import Path
from utz import o
from utz.process import line
from sys import stderr

from .err import OK, RAISE, WARN
from .version import get_version
version = get_version()

DEFAULT_IMAGE_REPO = 'runsascoded/gsmo'
DEFAULT_IMAGE = f'{DEFAULT_IMAGE_REPO}:{version}'
DEFAULT_DIND_IMAGE = f'{DEFAULT_IMAGE_REPO}:dind_{version}'
IMAGE_HOME = '/home'
DEFAULT_CONFIG_FILE = 'gsmo.yml'
DEFAULT_SRC_DIR_NAME = 'src'
DEFAULT_SRC_MOUNT_DIR = f'/{DEFAULT_SRC_DIR_NAME}'
DEFAULT_RUN_NB = 'run.ipynb'
DEFAULT_NB_DIR = 'nbs'

DEFAULT_USER = 'gsmo'
DEFAULT_GROUP = 'gsmo'

GSMO_DIR_NAME = 'gsmo'
GSMO_DIR = f'/{GSMO_DIR_NAME}'
GH_REPO = 'runsascoded/gsmo'


class Config:
    def __init__(self, args=None):
        self.args = args
        if exists(DEFAULT_CONFIG_FILE):
            import yaml
            with open(DEFAULT_CONFIG_FILE,'r') as f:
                self.config = o(yaml.safe_load(f))
        else:
            self.config = o()

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


def clean_group(group, err=RAISE):
    import grp
    group = str(group)
    if group.startswith(':'):
        group = group[1:]
        gid = grp.getgrgid(group).gr_gid
    elif exists(group):
        g = line('stat','-c','%g',group)
        return g
    else:
        try:
            gid = grp.getgrgid(group).gr_gid
        except Exception:
            try:
                gid = grp.getgrnam(group).gr_gid
            except Exception:
                msg = 'No group found for %s\n' % group
                if err == RAISE:
                    raise RuntimeError(msg)
                if err == WARN:
                    stderr.write('%s\n' % msg)
                return None
    return str(gid)
