from __future__ import (
    absolute_import,
    unicode_literals,
)

import pytest

from pysoa.client.client import Client
from pysoa.common.errors import Error
from pysoa.common.types import ActionResponse
from pysoa.test.assertions import (
    raises_call_action_error,
    raises_error_codes,
    raises_field_errors,
    raises_only_error_codes,
    raises_only_field_errors,
)


@pytest.fixture(scope='module')
def test_error():
    return Error(code='TEST', message='test fail')


@pytest.fixture(scope='module')
def auth_missing_error():
    return Error(code='AUTH_MISSING', message='where did ur auth go')


@pytest.fixture(scope='module')
def invalid_event_id_field_error():
    return Error(code='INVALID', field='event_id', message='bad event_id')


@pytest.fixture(scope='module')
def unknown_event_id_field_error():
    return Error(code='UNKNOWN', field='event_id', message='bad event_id')


@pytest.fixture(scope='module')
def invalid_organization_id_field_error():
    return Error(code='INVALID', field='organization_id', message='bad organization_id')


def test_raises_call_action_error_on_error(test_error):
    errors = [test_error]
    with raises_call_action_error() as exc_info:
        raise Client.CallActionError(
            actions=[ActionResponse(action='', errors=errors)]
        )

    assert exc_info.soa_errors == errors


def test_raises_call_action_error_no_error():
    with pytest.raises(pytest.raises.Exception):
        with raises_call_action_error():
            pass  # no error here means raises_call_action_error will fail


@pytest.mark.parametrize('exception_cls', [RuntimeError, ZeroDivisionError, Exception])
def test_raises_call_action_error_different_error(exception_cls):
    with pytest.raises(exception_cls):
        with raises_call_action_error():
            raise exception_cls()


def test_raises_error_codes_on_match(test_error):
    errors = [test_error]
    with raises_error_codes('TEST') as exc_info:
        raise Client.CallActionError(
            actions=[ActionResponse(action='', errors=errors)]
        )

    assert exc_info.soa_errors == errors


@pytest.mark.parametrize('codes', [
    ['TEST', 'AUTH_MISSING'],
    ['TEST', 'AUTH_MISSING', 'UNAUTHORIZED']
])
def test_raises_error_codes_multiple(codes):
    errors = [Error(code=code, message='bam') for code in codes]
    with raises_error_codes(['TEST', 'AUTH_MISSING']) as exc_info:
        raise Client.CallActionError(
            actions=[ActionResponse(action='', errors=errors)]
        )

    assert exc_info.soa_errors == errors


@pytest.mark.parametrize('codes', [
    ['TEST'],
    ['TEST', 'UNAUTHORIZED']
])
def test_raises_error_codes_missing(codes):
    errors = [Error(code=code, message='bam') for code in codes]
    with pytest.raises(pytest.raises.Exception):
        with raises_error_codes(['AUTH_MISSING']):
            raise Client.CallActionError(
                actions=[ActionResponse(action='', errors=errors)]
            )


def test_raises_error_codes_no_error():
    with pytest.raises(pytest.raises.Exception):
        with raises_error_codes(['TEST']):
            pass


def test_raises_error_codes_unexpected_only(test_error, auth_missing_error):
    errors = [test_error, auth_missing_error]
    with pytest.raises(pytest.raises.Exception):
        with raises_error_codes(['AUTH_MISSING'], only=True):
            raise Client.CallActionError(
                actions=[ActionResponse(action='', errors=errors)]
            )


def test_raises_only_error_codes_match(test_error, auth_missing_error):
    errors = [test_error, auth_missing_error]
    with raises_only_error_codes(['AUTH_MISSING', 'TEST']) as exc_info:
        raise Client.CallActionError(
            actions=[ActionResponse(action='', errors=errors)]
        )

    assert exc_info.soa_errors == errors


def test_raises_only_error_codes_unexpected(test_error, auth_missing_error):
    errors = [test_error, auth_missing_error]
    with pytest.raises(pytest.raises.Exception):
        with raises_only_error_codes(['AUTH_MISSING']):
            raise Client.CallActionError(
                actions=[ActionResponse(action='', errors=errors)]
            )


def test_raises_error_only_codes_unexpected_field_error(invalid_event_id_field_error, auth_missing_error):
    errors = [invalid_event_id_field_error, auth_missing_error]
    with pytest.raises(pytest.raises.Exception):
        with raises_only_error_codes('AUTH_MISSING'):
            raise Client.CallActionError(
                actions=[ActionResponse(action='', errors=errors)]
            )


def test_raises_error_only_codes_unexpected_missing(test_error, auth_missing_error):
    errors = [test_error, auth_missing_error]
    with pytest.raises(pytest.raises.Exception):
        with raises_only_error_codes('UNAUTHORIZED'):
            raise Client.CallActionError(
                actions=[ActionResponse(action='', errors=errors)]
            )


def test_raises_field_errors_on_match(invalid_event_id_field_error):
    errors = [invalid_event_id_field_error]
    with raises_field_errors({'event_id': 'INVALID'}) as exc_info:
        raise Client.CallActionError(
            actions=[ActionResponse(action='', errors=errors)]
        )

    assert exc_info.soa_errors == errors


@pytest.mark.parametrize('codes', [
    [('event_id', 'UNKNOWN'), ('organization_id', 'INVALID')],
    [('event_id', 'UNKNOWN'), ('event_id', 'INVALID'), ('organization_id', 'INVALID')],
])
def test_raises_field_errors_match_multiple(codes):
    errors = [Error(code=code, field=field, message='bam') for field, code in codes]
    with raises_field_errors({'event_id': 'UNKNOWN', 'organization_id': 'INVALID'}) as exc_info:
        raise Client.CallActionError(
            actions=[ActionResponse(action='', errors=errors)]
        )

    assert exc_info.soa_errors == errors


@pytest.mark.parametrize('code, field', [
    ('UNKNOWN', 'organization_id'),
    ('INVALID', 'event_id'),
])
def test_raises_field_errors_missing(code, field):
    errors = [
        Error(code=code, message='test fail', field=field),
    ]
    with pytest.raises(pytest.raises.Exception):
        with raises_field_errors({'event_id': 'UNKNOWN'}):
            raise Client.CallActionError(
                actions=[ActionResponse(action='', errors=errors)]
            )


def test_raises_field_errors_no_error():
    with pytest.raises(pytest.raises.Exception):
        with raises_field_errors({'organization_id': 'UNKNOWN'}):
            pass


def test_raises_field_errors_unexpected_only(invalid_event_id_field_error, unknown_event_id_field_error):
    errors = [
        invalid_event_id_field_error,
        unknown_event_id_field_error,
    ]
    with pytest.raises(pytest.raises.Exception):
        with raises_field_errors({'event_id': ['UNKNOWN']}, only=True):
            raise Client.CallActionError(
                actions=[ActionResponse(action='', errors=errors)]
            )


def test_raises_only_field_errors_match(invalid_event_id_field_error, unknown_event_id_field_error):
    errors = [
        invalid_event_id_field_error,
        unknown_event_id_field_error,
    ]
    with raises_only_field_errors({'event_id': ['UNKNOWN', 'INVALID']}) as exc_info:
        raise Client.CallActionError(
            actions=[ActionResponse(action='', errors=errors)]
        )

    assert exc_info.soa_errors == errors


def test_raises_only_field_errors_unexpected(unknown_event_id_field_error, invalid_organization_id_field_error):
    errors = [
        unknown_event_id_field_error,
        invalid_organization_id_field_error,
    ]
    with pytest.raises(pytest.raises.Exception):
        with raises_only_field_errors({'organization_id': 'INVALID'}):
            raise Client.CallActionError(
                actions=[ActionResponse(action='', errors=errors)]
            )


def test_raises_only_field_errors_unexpected_error(auth_missing_error, invalid_organization_id_field_error):
    errors = [
        auth_missing_error,
        invalid_organization_id_field_error,
    ]
    with pytest.raises(pytest.raises.Exception):
        with raises_only_field_errors({'organization_id': 'INVALID'}):
            raise Client.CallActionError(
                actions=[ActionResponse(action='', errors=errors)]
            )


def test_raises_only_field_errors_unexpected_missing(unknown_event_id_field_error, invalid_organization_id_field_error):
    errors = [
        unknown_event_id_field_error,
        invalid_organization_id_field_error,
    ]
    with pytest.raises(pytest.raises.Exception):
        with raises_only_field_errors({'event_id': 'MISSING'}):
            raise Client.CallActionError(
                actions=[ActionResponse(action='', errors=errors)]
            )
