import pytest
from re import escape

from gsmo.cli import Spec


def test_spec():
    def check(args, tpl, s):
        spec = Spec(*args)
        spec2 = Spec(spec)
        assert spec2 is spec
        assert tuple(spec) == tpl
        assert str(spec) == s

    check ((), (), '')
    check ((None,), (), '')
    check ((None, None,), (), '')
    check ((None, None, None,), (), '')

    check(('origin/aaa:bbb',), ('origin', 'aaa:bbb'), 'origin/aaa:bbb')
    check(('origin','aaa:bbb',), ('origin', 'aaa:bbb'), 'origin/aaa:bbb')
    check(('origin','aaa','bbb',), ('origin', 'aaa:bbb'), 'origin/aaa:bbb')
    check(('origin/aaa:bbb!',), ('origin', 'aaa:bbb'), 'origin/aaa:bbb!')
    check(('origin','aaa:bbb!',), ('origin', 'aaa:bbb'), 'origin/aaa:bbb!')
    check(('origin','aaa','bbb',True), ('origin', 'aaa:bbb'), 'origin/aaa:bbb!')

    check(('origin/aaa',), ('origin', 'aaa'), 'origin/aaa')
    check(('origin','aaa',), ('origin', 'aaa'), 'origin/aaa')
    check(('origin','aaa','aaa',), ('origin', 'aaa'), 'origin/aaa')
    check(('origin/aaa!',), ('origin', 'aaa'), 'origin/aaa!')
    check(('origin','aaa!',), ('origin', 'aaa'), 'origin/aaa!')
    check(('origin','aaa','aaa',True), ('origin', 'aaa'), 'origin/aaa!')

    check(('origin',), ('origin',), 'origin')
    with pytest.raises(ValueError) as e:
        check(('origin!',), (), '')
    e.match('(src && dst)')

    check(('origin/aaa:',), ('origin', 'aaa:'), 'origin/aaa:')
    check(('origin','aaa:',), ('origin', 'aaa:'), 'origin/aaa:')
    check(('origin','aaa',''), ('origin', 'aaa:'), 'origin/aaa:')
    check(('origin','aaa',None), ('origin', 'aaa:'), 'origin/aaa:')

    for args in (
        ('origin/aaa:!',),
        ('origin','aaa:!',),
        ('origin','aaa','',True),
        ('origin','aaa',None,True),
    ):
        with pytest.raises(ValueError) as e:
            check(args, (), '')
        e.match('src && dst')

    check(('origin/:bbb',), ('origin', ':bbb'), 'origin/:bbb')
    check(('origin',':bbb',), ('origin', ':bbb'), 'origin/:bbb')
    check(('origin','','bbb'), ('origin', ':bbb'), 'origin/:bbb')
    check(('origin',None,'bbb'), ('origin', ':bbb'), 'origin/:bbb')

    for args in (
        ('origin/:bbb!',),
        ('origin',':bbb!',),
        ('origin','','bbb',True,),
        ('origin',None,'bbb!',True,),
    ):
        with pytest.raises(ValueError) as e:
            check(args, (), '')
        e.match('src && dst')

    with pytest.raises(ValueError) as e:
        check((None, 'aaa', None), (), '')
    e.match('Invalid spec: (src || dst)')

    with pytest.raises(ValueError) as e:
        check(('origin', 'aaa', 'bbb', 'ccc'), (), '')
    e.match(escape('Invalid `pull` param'))

    with pytest.raises(ValueError) as e:
        check(('origin', 'aaa', 'bbb', 'ccc', 'ddd'), (), '')
    e.match(escape('too many values to unpack (expected 1)'))
