from re import fullmatch


def w(name, ch=r'\w'):
    return f'(?P<{name}>{ch}+)'
user_rgx = w("user")
domain_rgx = w("domain", r"[A-Za-z0-9\-\.]")
ssh_host_rgx = '(?P<host>(?:%s@)?%s)' % (user_rgx, domain_rgx)
path_chars = r"[A-Za-z0-9\-\./]"
path_rgx = w("path", path_chars)
branch_rgx = w("branch", r"[\w\-]")
port_rgx = w('port',r'\d')

GIT_SSH_URL_REGEX = '(?:ssh://)?%s:%s(?:@%s)?' % (ssh_host_rgx, path_rgx, branch_rgx)
GIT_HTTP_URL_REGEX = '(?:https?://)?%s(?::%s)?:%s(?:@%s)?' % (domain_rgx, port_rgx, path_rgx, branch_rgx)


class Idem(type):
    def __call__(cls, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], Spec):
            return args[0]
        self = cls.__new__(cls, *args, **kwargs)
        self.__init__(*args, **kwargs)
        return self

    def __init__(cls, name, bases, attributes):
        super().__init__(name, bases, attributes)


class Spec(metaclass=Idem):
    '''Wrap a Git refspec ("<remote>/<src>:<dst>"; <src>/<dst> optional) for use with `git push`, providing str and
    tuple converters and extra syntax for configuring post-push working-tree syncing.

    Notably, a trailing "!" signals a `git push` target whose working tree should be additionally made to match the
    <dst> ref (e.g. by `push`ing <src> to a temporary branch on <remote>, then `cd`'ing (or `ssh`'ing) into <remote> and
    merging that temporary placeholder branch into <dst>).
    '''
    PULL_REGEX = '(?P<pull>\!)?'
    SRC_DST_REGEX = '(?P<src>[^:]*?)(?::(?P<dst>.*?))?'
    SPEC_REGEX = f'{SRC_DST_REGEX}{PULL_REGEX}'
    FULL_REGEX = f'(?P<remote>[^/]+?)(?:/{SRC_DST_REGEX})?{PULL_REGEX}'

    def _parse_spec(self, spec, full):
        self.pull = False
        if spec is None:
            (self.src, self.dst) = (None, None)
            if full:
                self.remote = None
            return
        if full:
            regex = self.FULL_REGEX
        else:
            regex = self.SPEC_REGEX
        if not (m := fullmatch(regex, spec)):
            raise ValueError(f'Invalid spec: {spec}')
        if full:
            self.remote = m['remote']
        self.src = m['src'] or None  # '' ⟶ None
        if m['dst'] is None:
            self.dst = self.src
        else:
            self.dst = m['dst'] or None  # '' ⟶ None
        if m['pull']:
            self.pull = True

    def __init__(self, *args):
        self.remote = None
        self.src = None
        self.dst = None
        self.pull = False
        if args:
            (arg, *args) = args
            if not args:
                if arg is not None:
                    self._parse_spec(arg, full=True)
            else:
                (self.remote, arg, *args) = (arg, *args)
                if not args:
                    self._parse_spec(arg, full=False)
                else:
                    (self.src, self.dst, *args) = (arg, *args)
                    if args:
                        (self.pull,) = args
                        if not (self.pull is None or isinstance(self.pull, bool)):
                            raise ValueError(f'Invalid `pull` param: {self.pull}')
                    else:
                        self.pull = False

            if self.remote is None and (self.src is not None or self.dst is not None):
                raise ValueError(f'Invalid spec: (src || dst) ⟹ remote. ({self.remote=}, {self.src=}, {self.dst=})')

            # in `pull` mode, both or neither of {src,dst} must be set
            if self.pull and (bool(self.src) != bool(self.dst)):
                raise ValueError(f'pull ⟹ (src && dst): ({self.remote=}, {self.src=}, {self.dst=}, {self.pull=})')

    def __str__(self):
        tpl = tuple(self)
        if not tpl:
            assert not self.pull
            return ''
        if len(tpl) == 2:
            s = f'{tpl[0]}/{tpl[1]}'
        elif len(tpl) == 1:
            (remote,) = tpl
            s = remote
        else:
            raise RuntimeError(f'Invalid spec tuple: {tpl}')
        if self.pull:
            s += '!'
        return s

    def __repr__(self): return str(self)

    def __iter__(self):
        '''Return arguments suitable for passing to `git push`.

        Examples:
        - 0 args (corresponds to `git push`)
        - 1 arg (`git push origin`)
        - 2 args (`git push origin aaa` or `git push origin aaa:bbb`)
        '''
        if self.remote:
            yield self.remote
            if self.src or self.dst:
                if self.src == self.dst:
                    yield self.src
                else:
                    yield f'{self.src or ""}:{self.dst or ""}'


