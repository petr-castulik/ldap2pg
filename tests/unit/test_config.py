from __future__ import unicode_literals

import pytest


def test_mapping():
    from ldap2pg.config import Mapping

    m = Mapping('sync_map', env=None)
    v = m.process(default='defval', file_config=dict(), environ=dict())
    assert 'defval' == v

    m = Mapping('ldap:password', secret=True)
    assert 'LDAP_PASSWORD' == m.env

    # Nothing in either file or env -> default
    v = m.process(default='DEFAULT', file_config=dict(), environ=dict())
    assert 'DEFAULT' == v

    with pytest.raises(ValueError):
        # Something in file but it's not secure
        m.process(
            default='DEFAULT',
            file_config=dict(
                world_readable=True,
                ldap=dict(password='unsecure'),
            ),
            environ=dict(),
        )

    # File is unsecure but env var overrides value and error.
    v = m.process(
        default='DEFAULT',
        file_config=dict(ldap=dict(password='unsecure')),
        environ=dict(LDAP_PASSWORD='fromenv'),
    )
    assert 'fromenv' == v

    # File is secure, use it.
    v = m.process(
        default='DEFAULT',
        file_config=dict(world_readable=False, ldap=dict(password='53cUr3!')),
        environ=dict(),
    )
    assert '53cUr3!' == v

    m = Mapping('postgres:dsn', secret="password=")
    with pytest.raises(ValueError):
        # Something in file but it's not secure
        m.process(
            default='DEFAULT',
            file_config=dict(
                world_readable=True,
                postgres=dict(dsn='password=unsecure'),
            ),
            environ=dict(),
        )


def test_processor():
    from ldap2pg.config import Mapping

    m = Mapping('dry', processor=bool)
    v = m.process(default=True, file_config=dict(dry=0), environ=dict())

    assert v is False


def test_process_syncmap():
    from ldap2pg.config import syncmap

    # Canonical case.
    raw = dict(
        ldap=dict(
            base='dc=unit',
            attribute='cn',
        ),
        role=dict(),
    )

    v = syncmap(raw)

    assert isinstance(v, list)
    assert 1 == len(v)
    assert 'attributes' in v[0]['ldap']
    assert 'attribute' not in v[0]['ldap']
    assert 'filter' in v[0]['ldap']
    assert 'roles' in v[0]

    # Missing rules
    raw = dict(ldap=dict(base='dc=unit', attribute='cn'))
    with pytest.raises(ValueError):
        syncmap(raw)


def test_process_rolerule():
    from ldap2pg.config import rolerule

    rule = rolerule(dict(options='LOGIN SUPERUSER'))
    assert rule['options']['LOGIN'] is True
    assert rule['options']['SUPERUSER'] is True

    rule = rolerule(dict(options=['LOGIN', 'SUPERUSER']))
    assert rule['options']['LOGIN'] is True
    assert rule['options']['SUPERUSER'] is True

    rule = rolerule(dict(options=['NOLOGIN', 'SUPERUSER']))
    assert rule['options']['LOGIN'] is False
    assert rule['options']['SUPERUSER'] is True


def test_find_filename(mocker):
    stat = mocker.patch('ldap2pg.config.stat')

    from ldap2pg.config import Configuration, NoConfigurationError

    config = Configuration()

    def mk_oserror(errno=None):
        e = OSError()
        e.errno = errno
        return e

    # Search default path
    stat.side_effect = [
        mk_oserror(),
        mk_oserror(13),
        mocker.Mock(st_mode=0o600),
    ]
    filename, mode = config.find_filename(environ=dict())
    assert config._file_candidates[2] == filename
    assert 0o600 == mode

    # Read from env var LDAP2PG_CONFIG
    stat.reset_mock()
    stat.side_effect = [
        OSError(),
        AssertionError("Not reached."),
    ]
    with pytest.raises(NoConfigurationError):
        config.find_filename(environ=dict(LDAP2PG_CONFIG='my.yml'))


def test_merge_and_mappings():
    from ldap2pg.config import Configuration

    # Noop
    config = Configuration()
    with pytest.raises(ValueError):
        config.merge(file_config={}, environ={})

    # Minimal configuration
    minimal_config = dict(
        ldap=dict(host='confighost'),
        sync_map=dict(ldap=dict(), role=dict()),
    )
    config.merge(
        file_config=minimal_config,
        environ=dict(),
    )
    config.merge(
        file_config=minimal_config,
        environ=dict(LDAP_PASSWORD='envpass', PGDSN='envdsn'),
    )
    assert 'confighost' == config['ldap']['host']
    assert 'envpass' == config['ldap']['password']
    assert 'envdsn' == config['postgres']['dsn']


def test_security():
    from ldap2pg.config import Configuration

    config = Configuration()

    minimal_config = dict(
        ldap=dict(host='confighost'),
        sync_map=dict(ldap=dict(), role=dict()),
    )

    with pytest.raises(ValueError):
        config.merge(environ=dict(), file_config=dict(
            minimal_config,
            ldap=dict(password='unsecure'),
        ))

    with pytest.raises(ValueError):
        # Refuse world readable postgres URI with password
        config.merge(environ=dict(), file_config=dict(
            minimal_config,
            postgres=dict(dsn='password=unsecure'),
        ))

    with pytest.raises(ValueError):
        # Refuse world readable postgres URI with password
        config.merge(environ=dict(), file_config=dict(
            minimal_config,
            postgres=dict(dsn='postgres://u:unsecure@h'),
        ))

    config.merge(environ=dict(), file_config=dict(
        minimal_config,
        postgres=dict(dsn='postgres://u@h'),
    ))


def test_read_yml():
    from io import StringIO

    from ldap2pg.config import Configuration, ConfigurationError

    config = Configuration()

    # Deny list file
    fo = StringIO("- listentry")
    with pytest.raises(ConfigurationError):
        config.read(fo, mode=0o0)

    fo = StringIO("entry: value")
    payload = config.read(fo, mode=0o644)
    assert 'entry' in payload
    assert payload['world_readable'] is True

    # Accept empty file (e.g. /dev/null)
    fo = StringIO("")
    payload = config.read(fo, mode=0o600)
    assert payload['world_readable'] is False


def test_load(mocker):
    environ = dict()
    mocker.patch('ldap2pg.config.os.environ', environ)
    ff = mocker.patch('ldap2pg.config.Configuration.find_filename')
    read = mocker.patch('ldap2pg.config.Configuration.read')
    mocker.patch('ldap2pg.config.open', create=True)

    from ldap2pg.config import (
        Configuration,
        ConfigurationError,
        NoConfigurationError,
    )

    config = Configuration()

    ff.side_effect = NoConfigurationError()
    # Missing sync_map
    with pytest.raises(ConfigurationError):
        config.load()

    ff.side_effect = None
    # Find `filename.yml`
    ff.return_value = ['filename.yml', 0o0]
    # ...containing mapping
    read.return_value = dict(sync_map=dict(ldap=dict(), role=dict()))
    # send one env var for LDAP bind
    environ.update(dict(LDAP_BIND='envbind'))

    config.load()

    assert 'envbind' == config['ldap']['bind']
    assert 1 == len(config['sync_map'])
    assert 'ldap' in config['sync_map'][0]