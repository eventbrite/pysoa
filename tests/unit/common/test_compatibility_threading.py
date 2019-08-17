from __future__ import (
    absolute_import,
    unicode_literals,
)

import threading
import time

import pytest
import six

from pysoa.common.compatibility import ContextVar


try:
    import contextvars
except ImportError:
    contextvars = None


def test_one_thread():
    var = ContextVar('test_one_thread1')

    with pytest.raises(LookupError) as error_context:
        var.get()

    if six.PY2:
        assert error_context.value.args[0] is var
        assert "pysoa.common.compatibility.ContextVar name='test_one_thread1' at " in repr(var)
        assert isinstance(var.variable, getattr(threading, 'local'))
    else:
        assert "ContextVar name='test_one_thread1' at " in repr(var)
        assert isinstance(var.variable, contextvars.ContextVar)

    assert var.get('default1') == 'default1'
    assert var.get(default='default2') == 'default2'

    var.set('set1')
    assert var.get() == 'set1'

    var = ContextVar('test_one_thread2', 'default3')

    assert var.get() == 'default3'
    assert var.get('default4') == 'default4'

    var.set('set2')
    assert var.get() == 'set2'

    var = ContextVar('test_one_thread3', default='default5')

    assert var.get() == 'default5'
    assert var.get('default6') == 'default6'

    var.set('set3')
    assert var.get() == 'set3'


def test_multiple_threads():
    var1 = ContextVar('test_multiple_threads1')
    var2 = ContextVar('test_multiple_threads1')

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
    }

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
