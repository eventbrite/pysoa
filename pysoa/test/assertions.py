from __future__ import (
    absolute_import,
    unicode_literals,
)

import contextlib

import pytest
import six

from pysoa.client import Client


@contextlib.contextmanager
def raises_call_action_error(**kwargs):
    with pytest.raises(Client.CallActionError, **kwargs) as exc_info:
        yield exc_info

    exc_info.soa_errors = exc_info.value.actions[0].errors


@contextlib.contextmanager
def raises_error_codes(error_codes, only=False, **kwargs):
    with raises_call_action_error(**kwargs) as exc_info:
        yield exc_info

    raised_errors = exc_info.soa_errors

    if not isinstance(error_codes, set):
        if isinstance(error_codes, list):
            error_codes = set(error_codes)
        else:
            error_codes = {error_codes}

    unexpected_errors = []
    missing_errors = []

    # Go through all the errors returned by the action, mark any that are unexpected, remove any that match
    for error in raised_errors:
        if getattr(error, 'field', None):
            unexpected_errors.append({error.field: (error.code, error.message)})
            continue

        if error.code not in error_codes:
            unexpected_errors.append((error.code, error.message))
            continue

        error_codes.remove(error.code)

    # Go through all the remaining expected errors that weren't matched
    for error in error_codes:
        missing_errors.append(error)

    error_msg = ''
    if missing_errors:
        error_msg = 'Expected errors not found in response: {}'.format(str(missing_errors))

    if only and unexpected_errors:
        if error_msg:
            error_msg += '\n'
        error_msg += 'Unexpected errors found in response: {}'.format(str(unexpected_errors))

    if error_msg:
        # If we have any cause to error, do so
        pytest.fail(error_msg)


def raises_only_error_codes(error_codes, **kwargs):
    return raises_error_codes(error_codes, only=True, **kwargs)


@contextlib.contextmanager
def raises_field_errors(field_errors, only=False, **kwargs):
    with raises_call_action_error(**kwargs) as exc_info:
        yield exc_info

    raised_errors = exc_info.soa_errors
    unexpected_errors = []
    missing_errors = []

    # Provide the flexibility for them to pass it a set or list of error codes, or a single code, per field
    for field, errors in six.iteritems(field_errors):
        if not isinstance(errors, set):
            if isinstance(errors, list):
                field_errors[field] = set(errors)
            else:
                field_errors[field] = {errors}

    # Go through all the errors returned by the action, mark any that are unexpected, remove any that match
    for error in raised_errors:
        if not getattr(error, 'field', None):
            unexpected_errors.append((error.code, error.message))
            continue

        if error.field not in field_errors:
            unexpected_errors.append({error.field: (error.code, error.message)})
            continue

        if error.code not in field_errors[error.field]:
            unexpected_errors.append({error.field: (error.code, error.message)})
            continue

        field_errors[error.field].remove(error.code)
        if not field_errors[error.field]:
            del field_errors[error.field]

    # Go through all the remaining expected errors that weren't matched
    for field, errors in six.iteritems(field_errors):
        for error in errors:
            missing_errors.append({field: error})

    error_msg = ''
    if missing_errors:
        error_msg = 'Expected field errors not found in response: {}'.format(str(missing_errors))

    if only and unexpected_errors:
        if error_msg:
            error_msg += '\n'
        error_msg += 'Unexpected errors found in response: {}'.format(str(unexpected_errors))

    if error_msg:
        # If we have any cause to error, do so
        pytest.fail(error_msg)


def raises_only_field_errors(field_errors, **kwargs):
    return raises_field_errors(field_errors, only=True, **kwargs)
