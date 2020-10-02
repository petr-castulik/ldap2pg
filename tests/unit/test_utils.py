# coding: utf-8

from __future__ import unicode_literals

from time import sleep

import pytest


def test_deep_getset():
    from ldap2pg.utils import deepget, deepset

    a = dict()

    deepset(a, 'toto:tata', 1)

    assert 1 == a['toto']['tata']
    assert 1 == deepget(a, 'toto:tata')

    with pytest.raises(KeyError):
        deepget(a, 'toto:titi')


def test_decode_decode():
    from ldap2pg.utils import decode_value, encode_value

    decoded = {'é': [('é', 0xcafe)], 0xdead: None}
    eacute = 'é'.encode('utf-8')
    encoded = {
        eacute: [(eacute, 0xcafe)],
        0xdead: None,
    }

    assert decoded == decode_value(encoded)
    assert encoded == encode_value(decoded)
    assert 'décoded' == decode_value('décoded')


def test_ensure_unicode():
    from ldap2pg.utils import ensure_unicode, PY2

    assert u"accentué" == ensure_unicode(u"accentué")
    assert u"accentué" == ensure_unicode(u"accentué".encode('utf-8'))
    assert u"accentué" == ensure_unicode(Exception(u"accentué"))
    e = Exception(u"accentué".encode('utf-8'))
    if PY2:
        wanted = u"accentué"
    else:
        wanted = u"%r" % u"accentué".encode('utf-8')
    assert wanted == ensure_unicode(e)


def test_lower_keys():
    from ldap2pg.utils import lower_keys

    dict_ = lower_keys({'sAMAccountName': 'alice'})

    assert 'samaccountname' in dict_


def test_make_map():
    from ldap2pg.utils import make_group_map

    values = dict(v0=0, v1=1)
    groups = dict(g0=['v0'], g1=['v1', 'g0'], g2=['g1', 'g0'])

    aliases = make_group_map(values, groups)

    wanted = dict(
        v0=['v0'],
        v1=['v1'],
        g0=['v0'],
        g1=['v0', 'v1'],
        g2=['v0', 'v1'],
    )

    assert wanted == aliases


def test_iter_deep_keys():
    from ldap2pg.utils import iter_deep_keys

    data = dict(prefix=dict(subkey="Value"), key="value")
    keys = list(iter_deep_keys(data))

    assert 2 == len(keys)
    assert "prefix:subkey" in keys
    assert "key" in keys


def test_timer():
    from ldap2pg.utils import Timer

    my = Timer()
    assert repr(my)

    # Init checks
    assert 0 == my.delta.seconds
    assert 0 == my.delta.microseconds

    # Just do nothing.
    with my:
        pass
    assert my.delta.microseconds

    # Ensure delta is increased.
    first = my.delta.microseconds
    with my:
        # For the test, we only need to waste 1ms. Actually the syscall is
        # enough.
        sleep(0.00001)
    assert my.delta.microseconds > first

    # Time iteration
    for _ in my.time_iter(iter([0, 1])):
        pass


def test_user_error_wrap():
    from ldap2pg.utils import UserError

    e = UserError.wrap("""\
    Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec tortor odio, volutpat non volutpat vitae, mollis at felis. Sed placerat tincidunt
    auctor. Proin ipsum leo, dapibus ut suscipit sit amet, suscipit id massa. Fusce porta, nibh in ultricies mattis, sem magna ullamcorper sapien, quis
    efficitur velit erat vel nisl. Vestibulum facilisis eget augue sed tempor. Aenean porttitor rutrum odio in aliquet. Class aptent taciti sociosqu ad
    litora torquent per conubia nostra, per inceptos himenaeos. Etiam non massa quis ante blandit mattis. Morbi ut metus maximus, dignissim augue at,
    vestibulum leo. In at lectus vel arcu blandit vehicula sit amet et orci. Integer mollis in mi vel mattis.
    """)  # noqa

    lines = str(e).splitlines()
    assert 7 < len(lines)

    e = UserError.wrap("""\
    Lorem ipsum
    dolorsit amet,
    consectetur
    adipiscing elit.
    """)  # noqa

    lines = str(e).splitlines()
    assert 1 == len(lines)
