import contextlib
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Set,
    Tuple,
    Union,
    cast,
)

from _pytest._code.code import ExceptionInfo
import pytest

from pysoa.client.client import Client
from pysoa.common.errors import Error


__all__ = (
    'raises_call_action_error',
    'raises_error_codes',
    'raises_field_errors',
    'raises_only_error_codes',
    'raises_only_field_errors',
)


# Type-shed stub used only for casting to provide intelligent IDEs with `soa_errors`
class _PySOAExceptionInfo:
    soa_errors = []  # type: List[Error]


E = Tuple[str, str]


@contextlib.contextmanager
def raises_call_action_error(**kwargs):  # type: (**Any) -> Iterator[_PySOAExceptionInfo]
    with pytest.raises(Client.CallActionError, **kwargs) as exc_info:
        yield cast(_PySOAExceptionInfo, exc_info)

    exc_info.soa_errors = exc_info.value.actions[0].errors


@contextlib.contextmanager
def raises_error_codes(
    error_codes,  # type: Union[Iterable[str], str]
    only=False,  # type: bool
    **kwargs  # type: Any
):  # type: (...) -> Iterator[_PySOAExceptionInfo]
    with raises_call_action_error(**kwargs) as exc_info:
        yield exc_info

    raised_errors = exc_info.soa_errors

    if not isinstance(error_codes, Set):
        if not isinstance(error_codes, str):
            error_codes = set(error_codes)
        else:
            error_codes = {error_codes}

    unexpected_errors = []  # type: List[Union[E, Dict[str, E]]]
    missing_errors = []  # type: List[str]

    # Go through all the errors returned by the action, mark any that are unexpected, remove any that match
    for error in raised_errors:
        if hasattr(error, 'field') and error.field:
            unexpected_errors.append({error.field: (error.code, error.message)})
            continue

        if error.code not in error_codes:
            unexpected_errors.append((error.code, error.message))
            continue

        error_codes.remove(error.code)

    # Go through all the remaining expected errors that weren't matched
    for error_code in error_codes:
        missing_errors.append(error_code)

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


@contextlib.contextmanager
def raises_only_error_codes(
    error_codes,  # type: Union[Iterable[str], str]
    **kwargs  # type: Any
):  # type: (...) -> Iterator[_PySOAExceptionInfo]
    with raises_error_codes(error_codes, only=True, **kwargs) as exc_info:
        yield exc_info


@contextlib.contextmanager
def raises_field_errors(
    field_errors,  # type: Dict[str, Union[Iterable[str], str]]
    only=False,  # type: bool
    **kwargs  # type: Any
):  # type: (...) -> Iterator[_PySOAExceptionInfo]
    with raises_call_action_error(**kwargs) as exc_info:
        yield exc_info

    raised_errors = exc_info.soa_errors
    unexpected_errors = []  # type: List[Union[E, Dict[str, E]]]
    missing_errors = []  # type: List[Dict[str, str]]

    # Provide the flexibility for them to pass it a set or list of error codes, or a single code, per field
    new_field_errors = {}  # type: Dict[str, Set[str]]
    for field, errors in field_errors.items():
        if not isinstance(errors, Set):
            if not isinstance(errors, str):
                new_field_errors[field] = set(errors)
            else:
                new_field_errors[field] = {errors}
        else:
            new_field_errors[field] = errors

    # Go through all the errors returned by the action, mark any that are unexpected, remove any that match
    for error in raised_errors:
        if not hasattr(error, 'field') or not error.field:
            unexpected_errors.append((error.code, error.message))
            continue

        if error.field not in new_field_errors:
            unexpected_errors.append({error.field: (error.code, error.message)})
            continue

        if error.code not in new_field_errors[error.field]:
            unexpected_errors.append({error.field: (error.code, error.message)})
            continue

        new_field_errors[error.field].remove(error.code)
        if not new_field_errors[error.field]:
            del new_field_errors[error.field]

    # Go through all the remaining expected errors that weren't matched
    for field, error_codes in new_field_errors.items():
        for error_code in error_codes:
            missing_errors.append({field: error_code})

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


@contextlib.contextmanager
def raises_only_field_errors(
    field_errors,  # type: Dict[str, Union[Iterable[str], str]]
    **kwargs  # type: Any
):  # type: (...) -> Iterator[_PySOAExceptionInfo]
    with raises_field_errors(field_errors, only=True, **kwargs) as exc_info:
        yield exc_info
