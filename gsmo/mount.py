from os.path import abspath, basename, exists, expanduser, expandvars, isabs, isfile, join, realpath, sep
from sys import stderr
from typing import Iterable

from .err import OK, RAISE, WARN

class Mount:
    def __new__(cls, src, dst=None, err=RAISE, keep_missing=False):
        if not dst:
            if isinstance(src, Mount): return src
            pcs = src.split(':')
            if len(pcs) == 1:
                path = pcs[0]
                src = path
                if isabs(path):
                    dst = path
                else:
                    dst = '/%s' % path
            elif len(pcs) == 2:
                [src, dst] = pcs
            else:
                raise RuntimeError(f'Unrecognized mount spec: {src}')

        def expand(path): return expandvars(expanduser(path))
        src = abspath(expand(src))
        dst = expand(dst)

        if isfile(src) and dst.endswith(sep):
            dst = join(dst, basename(src))
        if not exists(src):
            if not keep_missing:
                msg = f"Mount src doesn't exist: {src}"
                if err == RAISE:
                    raise ValueError(msg)
                if err == WARN:
                    stderr.write('%s\n' % msg)
                else:
                    assert err == OK
                return None

        mnt = super(Mount, cls).__new__(cls)
        mnt.src = src
        mnt.dst = dst
        return mnt

    @property
    def args(self): return [ '-v', str(self) ]

    def  __str__(self): return f'{self.src}:{self.dst}'
    def __repr__(self): return str(self)


class Mounts:
    def __init__(self, mounts, err=RAISE, keep_missing=False):
        if isinstance(mounts, str):
            mounts = mounts.split(',')
        self.err = err
        self.keep_missing = keep_missing
        self.mounts = [ m for mount in mounts if (m := Mount(mount, err=err, keep_missing=keep_missing)) ]

    def __iadd__(self, other):
        if isinstance(other, Iterable):
            self.mounts += [ m for mnt in other if (m := Mount(mnt, err=self.err, keep_missing=self.keep_missing)) ]
        else:
            if isinstance(other, str):
                other = Mount(str, err=self.err, keep_missing=self.keep_missing)
            if other is None:
                return self
            if not isinstance(other, Mount):
                raise RuntimeError(f'Invalid mount: %s' % str(other))
            self.mounts.append(other)
        return self

    def __str__(self): return ','.join(str(mount) for mount in self.mounts)

    @property
    def src2dst(self): return { m.src: m.dst for m in self.mounts }

    @property
    def dst2src(self): return { m.dst: m.src for m in self.mounts }

    def args(self):
        return [ arg for mount in self.mounts for arg in mount.args ]
