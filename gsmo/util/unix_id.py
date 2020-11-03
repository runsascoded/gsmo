from functools import cached_property
from utz.process import line

class UnixId:
    @cached_property
    def uid(self): return line('id','-u')

    @cached_property
    def gid(self): return line('id','-g')

    @cached_property
    def user(self): return line('id','-un')

    @cached_property
    def group(self): return line('id','-gn')
