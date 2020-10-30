
from os.path import basename, exists, isfile, join, sep
from pathlib import Path
from sys import stderr
from utz.process import line


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
