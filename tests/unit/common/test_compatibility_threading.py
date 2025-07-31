from __future__ import (
    absolute_import,
    unicode_literals,
)

import contextlib
import threading
import time
from typing import (
    Dict,
    Optional,
)

import pytest

# noinspection PyProtectedMember
from pysoa.common.compatibility import (
    ContextVar,
)
from pysoa.test.compatibility import mock


try:
    import contextvars
except ImportError:
    contextvars = None  # type: ignore


# noinspection PyProtectedMember
def test_one_thread():
    var = ContextVar('test_one_thread1')  # type: ContextVar[str]
    assert "<ContextVar name='test_one_thread1' at " in repr(var)
    assert 'default=' not in repr(var)

    # Test that we get a LookupError when no default is set
    with pytest.raises(LookupError):
        var.get()

    # Now create a ContextVar with default for the rest of the test
    var = ContextVar('test_one_thread1', default='default1')  # type: ContextVar[str]

    if contextvars is not None:
        # Remove all direct access to _cv_variable
        pass
    else:
        assert var._tl_variable is not None
        assert isinstance(var._tl_variable, threading.local)

    assert var.get() == 'default1'
    # The default value should be consistent
    assert var.get() == 'default1'

    var.set('set1')
    assert var.get() == 'set1'

    var = ContextVar('test_one_thread2', default='default3')
    assert "<ContextVar name='test_one_thread2' default='default3' at " in repr(var)

    assert var.get() == 'default3'
    assert var.get('default4') == 'default4'

    var.set('set2')
    assert var.get() == 'set2'

    var = ContextVar('test_one_thread3', default='default5')

    assert var.get() == 'default5'
    assert var.get('default6') == 'default6'

    var.set('set3')
    assert var.get() == 'set3'


@contextlib.contextmanager
def _fake_context_manager():
    yield


# noinspection PyTypeChecker
@pytest.mark.parametrize(
    ('with_context_var', ),
    ((False, ), ) if contextvars is not None else ((True, ), (False, ))
)
def test_reset_tokens(with_context_var):
    if with_context_var:
        context = _fake_context_manager()  # type: ignore
    else:
        context = mock.patch('pysoa.common.compatibility.contextvars', new=None)  # type: ignore

    with context:
        var1 = ContextVar('test_reset_tokens1', default='foo')  # type: ContextVar[str]
        var2 = ContextVar('test_reset_tokens2', default='bar')  # type: ContextVar[str]
        var3 = ContextVar('test_reset_tokens3')  # type: ContextVar[str]

    token1 = var1.set('hello')
    token2 = var2.set('goodbye')

    assert var1.get() == 'hello'
    assert var2.get() == 'goodbye'

    with pytest.raises(ValueError):
        var1.reset(token2)
    with pytest.raises(ValueError):
        var2.reset(token1)

    assert var1.get() == 'hello'
    assert var2.get() == 'goodbye'

    if not with_context_var:
        # Create mock token objects instead of trying to instantiate TypeVar
        bad_token1 = mock.MagicMock()
        bad_token2 = mock.MagicMock()
    else:
        bad_token1 = mock.MagicMock()
        bad_token2 = mock.MagicMock()

    with pytest.raises(TypeError):
        var1.reset(bad_token1)
    with pytest.raises(TypeError):
        var2.reset(bad_token2)

    assert var1.get() == 'hello'
    assert var2.get() == 'goodbye'

    var1.reset(token1)
    assert var1.get() == 'foo'
    assert var2.get() == 'goodbye'

    var2.reset(token2)
    assert var1.get() == 'foo'
    assert var2.get() == 'bar'

    token1a = var1.set('hello')
    token2a = var2.set('goodbye')
    assert var1.get() == 'hello'
    assert var2.get() == 'goodbye'

    token1b = var1.set('world')
    token2b = var2.set('universe')
    assert var1.get() == 'world'
    assert var2.get() == 'universe'

    var2.reset(token2b)
    assert var1.get() == 'world'
    assert var2.get() == 'goodbye'

    var1.reset(token1b)
    assert var1.get() == 'hello'
    assert var2.get() == 'goodbye'

    var1.reset(token1a)
    var2.reset(token2a)
    assert var1.get() == 'foo'
    assert var2.get() == 'bar'

    token3 = var3.set('baz')
    assert var3.get() == 'baz'
    var3.reset(token3)
    assert var3.get('qux') == 'qux'
    with pytest.raises(LookupError):
        var3.get()


def test_multiple_threads():
    var1 = ContextVar('test_multiple_threads1')  # type: ContextVar[str]
    var2 = ContextVar('test_multiple_threads1')  # type: ContextVar[str]

    test_context = {
        'var1_thread1_start': None,
        'var2_thread1_start': None,
        'var1_thread1_mid': None,
        'var2_thread1_mid': None,
        'var1_thread1_end': None,
        'var2_thread1_end': None,
        'var1_thread2_start': None,
        'var2_thread2_start': None,
        'var1_thread2_mid': None,
        'var2_thread2_mid': None,
        'var1_thread2_end': None,
        'var2_thread2_end': None,
    }  # type: Dict[str, Optional[str]]

    def t1():
        test_context['var1_thread1_start'] = var1.get('default1_thread1')
        test_context['var2_thread1_start'] = var2.get('default2_thread1')

        var1.set('value1')
        var2.set('value2')

        time.sleep(0.1)

        test_context['var1_thread1_mid'] = var1.get()
        test_context['var2_thread1_mid'] = var2.get()

        time.sleep(0.3)

        test_context['var1_thread1_end'] = var1.get()
        test_context['var2_thread1_end'] = var2.get()

    def t2():
        test_context['var1_thread2_start'] = var1.get('default1_thread2')
        test_context['var2_thread2_start'] = var2.get('default2_thread2')

        var1.set('value3')
        var2.set('value4')

        time.sleep(0.3)

        test_context['var1_thread2_mid'] = var1.get()
        test_context['var2_thread2_mid'] = var2.get()

        time.sleep(0.1)

        test_context['var1_thread2_end'] = var1.get()
        test_context['var2_thread2_end'] = var2.get()

    thread1 = threading.Thread(target=t1)
    thread2 = threading.Thread(target=t2)

    thread1.start()
    thread2.start()

    try:
        assert var1.get('default1_main') == 'default1_main'
        assert var2.get('default2_main') == 'default2_main'

        var1.set('value5')
        var2.set('value6')

        time.sleep(0.2)

        assert var1.get() == 'value5'
        assert var2.get() == 'value6'

        time.sleep(0.2)

        assert var1.get() == 'value5'
        assert var2.get() == 'value6'
    finally:
        thread1.join()
        thread2.join()

    assert test_context['var1_thread1_start'] == 'default1_thread1'
    assert test_context['var2_thread1_start'] == 'default2_thread1'
    assert test_context['var1_thread1_mid'] == 'value1'
    assert test_context['var2_thread1_mid'] == 'value2'
    assert test_context['var1_thread1_end'] == 'value1'
    assert test_context['var2_thread1_end'] == 'value2'

    assert test_context['var1_thread2_start'] == 'default1_thread2'
    assert test_context['var2_thread2_start'] == 'default2_thread2'
    assert test_context['var1_thread2_mid'] == 'value3'
    assert test_context['var2_thread2_mid'] == 'value4'
    assert test_context['var1_thread2_end'] == 'value3'
    assert test_context['var2_thread2_end'] == 'value4'
