from __future__ import (
    absolute_import,
    unicode_literals,
)

import pprint

import six

from pysoa.test.plan.grammar.tools import (
    get_all_paths,
    path_get,
)


__test_plan_prune_traceback = True  # ensure code in this file is not included in failure stack traces


def make_error_msg_header(msg, header=None):
    if isinstance(msg, six.string_types):
        msg += '\n{}\nDATA ERROR:'.format('-' * 70)
    else:
        msg = ''
    if header:
        msg += '\n{}:'.format(header)
    return msg


def make_missing_error_message(missing, msg):
    msg += '\nMissing values:\n  `{missing}`'.format(
        missing='`\n  `'.join(sorted(missing)),
    )
    return msg


def make_mismatch_error_message(mismatch, mismatch_values, msg):
    msg += '\nMismatch values:\n  `{mismatch}`'.format(
        mismatch='`\n  `'.join(sorted(mismatch)),
    )

    # Mismatched fields
    msg += '\n'
    for field in sorted(mismatch_values.keys()):
        msg += (
            '\n`{field}` is incorrect:\n'
            '  Expected: {expected} ({expected_type})\n'
            '  Actual:   {actual} ({actual_type})\n'
        ).format(
            field=field,
            expected=mismatch_values[field]['expected'],
            expected_type=repr(type(mismatch_values[field]['expected'])),
            actual=mismatch_values[field]['actual'],
            actual_type=repr(type(mismatch_values[field]['actual'])),
        )

    return msg


def make_not_expected_error_message(not_expected_fields, msg):
    msg += '\nNot Expected fields present:\n   `{not_expected}`'.format(
        not_expected='`\n   `'.join(sorted(not_expected_fields)),
    )
    return msg


def make_failed_comparision_error_message(expected_key, expected, actual):
    return '\nFull body {expected_key}:\n{expected}\n\nFull body actual:\n{actual}\n'.format(
        expected_key=expected_key,
        expected=expected,
        actual=actual,
    )


def assert_subset_structure(expected, actual, subset_lists=False, msg=None):
    """
    Check that expected is a valid subset of actual, descend nested dicts
    """
    (missing, mismatch, mismatch_values, extra) = _check_subset_dict(
        expected,
        actual,
        subset_lists,
    )

    if missing or mismatch:
        msg = make_error_msg_header(msg)
        if missing:
            msg = make_missing_error_message(missing, msg)

        if mismatch:
            msg = make_mismatch_error_message(mismatch, mismatch_values, msg)

        # Expected values
        msg += make_failed_comparision_error_message(
            'expected',
            pprint.pformat(expected),
            pprint.pformat(actual),
        )

        raise AssertionError(msg)


def assert_expected_list_subset_of_actual(expected, actual, msg=None):
    _assert_lists_match_any_order(expected, actual, True, msg)


def assert_lists_match_any_order(expected, actual, msg=None):
    _assert_lists_match_any_order(expected, actual, False, msg)


def assert_not_expected(not_expected, actual, msg=None):
    """
    Assert that the given not_expected values are not in actual

    Note that this allows the keys to exist (be present) so long as they have different values.
    """
    (missing, mismatch, mismatch_values, extra) = _check_subset_dict(not_expected, actual, True)
    count = len(get_all_paths(not_expected))

    # For cases where we are sub-setting lists but the list actual is None, call mismatches good and count
    # them among the missing.
    for field, details in six.iteritems(mismatch_values):
        if details['actual'] is None and details['expected'] is not None:
            missing.append(field)

    if len(missing) != count:
        msg = make_error_msg_header(msg)
        msg = make_not_expected_error_message(
            set(get_all_paths(not_expected)) - set(missing),
            msg
        )

        msg += make_failed_comparision_error_message(
            'NOT expected',
            pprint.pformat(not_expected),
            pprint.pformat(actual),
        )
        raise AssertionError(msg)


def assert_not_present(not_present, actual, msg=None):
    """
    Assert that none of the keys in not_present exist in actual
    """
    present = []
    for path in get_all_paths(not_present):
        try:
            path_get(actual, path)
            present.append(path)
        except (KeyError, IndexError):
            pass

    if present:
        msg = make_error_msg_header(msg, 'Not present')
        msg += make_failed_comparision_error_message(
            'SHOULD NOT be present',
            pprint.pformat(present),
            pprint.pformat(actual),
        )
        raise AssertionError(msg)


def assert_actual_list_not_subset(not_expected, actual, msg=None):
    if not isinstance(not_expected, list):
        raise AssertionError('not-expected value is not a list')

    if not isinstance(actual, list):
        raise AssertionError('actual value is not a list')

    extras = []
    for not_expected_value in not_expected:
        if not_expected_value in actual:
            extras.append(not_expected_value)

    if extras:
        msg = make_error_msg_header(msg)
        msg += (
            '\nEncountered values were incorrect:\n'
            '  Expected not present: {expected} ({expected_type})\n'
            '  Actual:               {actual} ({actual_type})\n'
        ).format(
            expected=not_expected,
            expected_type=repr(type(not_expected)),
            actual=actual,
            actual_type=repr(type(actual)),
        )
        raise AssertionError(msg)


def assert_exact_structure(expected, actual, msg=None):
    """
    Check that expected is an exact match for actual
    """
    (missing, mismatch, mismatch_values, extra) = _check_subset_dict(
        expected,
        actual,
    )

    if missing or mismatch or extra:
        msg = make_error_msg_header(msg)
        if missing:
            msg = make_missing_error_message(missing, msg)

        if mismatch:
            msg = make_mismatch_error_message(mismatch, mismatch_values, msg)

        if extra:
            msg += '\nExtra values:\n'
            for field in extra:
                msg += '   `{field}`\n'.format(field=field)

        # Expected values
        msg += make_failed_comparision_error_message(
            'expected',
            pprint.pformat(expected),
            pprint.pformat(actual),
        )

        raise AssertionError(msg)


def _assert_lists_match_any_order(expected, actual, subset=False, msg=None):
    if not isinstance(expected, list):
        raise AssertionError('expected value is not a list')

    if not isinstance(actual, list):
        raise AssertionError('actual value is not a list')

    missing = []
    for expected_value in expected:
        if expected_value not in actual:
            missing.append(expected_value)

    if missing or (not subset and len(expected) != len(actual)):
        msg = make_error_msg_header(msg)
        msg += (
            '\nEncountered values were incorrect:\n'
            '  Expected {how}:{space} {expected} ({expected_type})\n'
            '  Actual:          {actual} ({actual_type})\n'
        ).format(
            how='subset' if subset else 'exact',
            space='' if subset else ' ',
            expected=expected,
            expected_type=repr(type(expected)),
            actual=actual,
            actual_type=repr(type(actual)),
        )
        raise AssertionError(msg)


def _compare_values(expected_val, actual_val, full_path=None, subset_lists=False):
    missing_keys = []
    extra_keys = []
    mismatching_keys = []
    mismatching_values = {}

    if isinstance(expected_val, dict) and isinstance(actual_val, dict):
        # Expected value is a dict, iterate recursively
        if expected_val:
            missing_sub_keys, mismatching_sub_keys, mismatching_sub_values, extra_sub_keys = _check_subset_dict(
                expected=expected_val,
                actual=actual_val,
                subset_lists=subset_lists,
                prefix=full_path,
            )
            missing_keys.extend(missing_sub_keys)
            mismatching_keys.extend(mismatching_sub_keys)
            mismatching_values.update(mismatching_sub_values)
            extra_keys.extend(extra_sub_keys)

        elif actual_val:
            # expected empty dict but got a populated one
            mismatching_keys.append(full_path)
            mismatching_values[full_path] = {
                'expected': expected_val,
                'actual': actual_val,
            }
            extra_keys.extend(get_all_paths(actual_val, current_path=full_path))

    elif isinstance(actual_val, list) and (subset_lists or isinstance(expected_val, list)):
        # Expected value is a list, iterate recursively
        if expected_val:
            missing_sub_keys, mismatching_sub_keys, mismatching_sub_values, extra_sub_keys = _check_subset_list(
                expected=expected_val,
                actual=actual_val,
                subset_lists=subset_lists,
                prefix=full_path,
            )
            missing_keys.extend(missing_sub_keys)
            mismatching_keys.extend(mismatching_sub_keys)
            mismatching_values.update(mismatching_sub_values)
            extra_keys.extend(extra_sub_keys)

        elif actual_val:
            # expected empty list but got a populated one
            mismatching_keys.append(full_path)
            mismatching_values[full_path] = {
                'expected': expected_val,
                'actual': actual_val,
            }
            extra_keys.extend(get_all_paths(actual_val, current_path=full_path))

    elif expected_val != actual_val:
        mismatching_keys.append(full_path)
        mismatching_values[full_path] = {
            'expected': expected_val,
            'actual': actual_val,
        }

    return sorted(missing_keys), sorted(mismatching_keys), mismatching_values, sorted(extra_keys)


def _check_subset_list(expected, actual, subset_lists=False, prefix=None):
    """
    Contrasts `expected` and `actual` lists and annotates missing/mismatching values.

    If `subset_lists` is `True`, then `expected` can be a single value to find in actual. If `False`, then `expected`
    and `actual` must be identical lists.
    """
    missing_keys = []
    extra_keys = []
    mismatching_keys = []
    mismatching_values = {}

    if not isinstance(actual, list):
        raise AssertionError('actual value is not a list')

    if not isinstance(expected, list):
        if subset_lists:
            if expected not in actual:
                missing_keys.append('{}.{}'.format(prefix, six.text_type(expected)))
        else:
            raise AssertionError('expected value is not a list')
    else:
        for i, expected_val in enumerate(expected):
            if subset_lists and not isinstance(expected_val, (dict, list)):
                if expected_val not in actual:
                    if prefix is not None:
                        missing_keys.append('{}.{}.{}'.format(prefix, i, six.text_type(expected_val)))
                    else:
                        missing_keys.append('{}.{}'.format(i, six.text_type(expected_val)))
                continue

            if prefix is not None:
                full_path = '{}.{}'.format(prefix, i)
            else:
                full_path = '{}'.format(i)

            try:
                actual_val = actual[i]
            except IndexError:
                missing_keys.append(full_path)
                continue

            missing_sub_keys, mismatching_sub_keys, mismatching_sub_values, extra_sub_keys = _compare_values(
                expected_val,
                actual_val,
                full_path,
                subset_lists=subset_lists
            )
            missing_keys.extend(missing_sub_keys)
            mismatching_keys.extend(mismatching_sub_keys)
            mismatching_values.update(mismatching_sub_values)
            extra_keys.extend(extra_sub_keys)
            continue

        # check for extra
        if len(expected) < len(actual):
            if prefix:
                extra_keys.extend(['{}.{}'.format(prefix, i) for i in range(len(expected), len(actual))])
            else:
                extra_keys.extend(['{}'.format(i) for i in range(len(expected), len(actual))])

    return sorted(missing_keys), sorted(mismatching_keys), mismatching_values, sorted(extra_keys)


def _check_subset_dict(expected, actual, subset_lists=False, prefix=None):
    """
    Contrasts `expected` and `actual` dicts and annotates missing/mismatching values.
    """
    missing_keys = []
    extra_keys = []
    mismatching_keys = []
    mismatching_values = {}

    if not isinstance(expected, dict):
        raise AssertionError('expected value is not a dict')

    if not isinstance(actual, dict):
        raise AssertionError('actual value is not a dict')

    for expected_key, expected_val in six.iteritems(expected):
        full_path = expected_key
        if '.' in full_path and '{' not in full_path:
            full_path = '{{{}}}'.format(full_path)
        if prefix is not None:
            full_path = '{}.{}'.format(prefix, full_path)

        if expected_key not in actual:
            for missing_sub_path in get_all_paths(expected_val):
                if missing_sub_path:
                    missing_keys.append('{}.{}'.format(full_path, missing_sub_path))
                else:
                    missing_keys.append(full_path)
            continue

        actual_val = actual[expected_key]
        missing_sub_keys, mismatching_sub_keys, mismatching_sub_values, extra_sub_keys = _compare_values(
            expected_val,
            actual_val,
            full_path,
            subset_lists=subset_lists
        )
        missing_keys.extend(missing_sub_keys)
        mismatching_keys.extend(mismatching_sub_keys)
        mismatching_values.update(mismatching_sub_values)
        extra_keys.extend(extra_sub_keys)
        continue

    # check for extra unexpected paths
    for actual_key, actual_val in six.iteritems(actual):
        full_path = actual_key
        if '.' in full_path and '{' not in full_path:
            full_path = '{{{}}}'.format(full_path)
        if prefix is not None:
            full_path = '{}.{}'.format(prefix, full_path)

        if actual_key not in expected:
            extra_keys.extend(get_all_paths(actual_val, current_path=full_path))
            continue

    return sorted(missing_keys), sorted(mismatching_keys), mismatching_values, sorted(extra_keys)
