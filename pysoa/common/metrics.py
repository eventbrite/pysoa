from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc
import enum

from conformity import fields
import six


@six.add_metaclass(abc.ABCMeta)
class Counter(object):
    """
    Defines an interface for incrementing a counter.
    """

    @abc.abstractmethod
    def increment(self, amount=1):
        """
        Increments the counter.

        :param amount: The amount by which to increment the counter, which must default to 1.
        """
        raise NotImplementedError()


class TimerResolution(enum.IntEnum):
    MILLISECONDS = 10**3
    MICROSECONDS = 10**6
    NANOSECONDS = 10**9


@six.add_metaclass(abc.ABCMeta)
class Timer(object):
    """
    Defines an interface for timing activity. Can be used as a context manager to time wrapped activity.
    """

    @abc.abstractmethod
    def start(self):
        """
        Starts the timer.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def stop(self):
        """
        Stops the timer.
        """
        raise NotImplementedError()

    def __enter__(self):
        """
        Starts the timer at the start of the context manager.
        """
        self.start()

    def __exit__(self, *_, **__):
        """
        Stops the timer at the end of the context manager. All parameters are ignored. Always returns ``False``.

        :return: ``False``
        :rtype: bool
        """
        self.stop()
        return False


@six.add_metaclass(abc.ABCMeta)
class MetricsRecorder(object):
    """
    Defines an interface for recording metrics. All metrics recorders registered with PySOA must implement this
    interface. Note that counters and timers with the same name will not be recorded. If your metrics backend needs
    timers to also have associated counters, your implementation of this recorder must take care of filling that gap.
    """

    @abc.abstractmethod
    def counter(self, name, **kwargs):
        """
        Returns a counter that can be incremented. Implementations do not have to return an instance of `Counter`, but
        they must at least return an object that matches the interface for `Counter`.

        :param name: The name of the counter
        :param kwargs: Any other arguments that may be needed

        :return: a counter object.
        :rtype: Counter
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def timer(self, name, resolution=TimerResolution.MILLISECONDS, **kwargs):
        """
        Returns a timer that can be started and stopped. Implementations do not have to return an instance of `Timer`,
        but they must at least return an object that matches the interface for `Timer`, including serving as a context
        manager.

        :param name: The name of the timer
        :param resolution: The resolution at which this timer should operate, defaulting to milliseconds. Its value
                           should be a `TimerResolution` or any other equivalent `IntEnum` whose values serve as
                           integer multipliers to convert decimal seconds to the corresponding units. It will only
                           ever be access as a keyword argument, never as a positional argument, so it is not necessary
                           for this to be the second positional argument in your equivalent recorder class.
        :type resolution: enum.IntEnum
        :param kwargs: Any other arguments that may be needed

        :return: a timer object
        :rtype: Timer
        """
        raise NotImplementedError()

    def commit(self):
        """
        Commits the recorded metrics, if necessary, to the storage medium in which they reside. Can simply be a
        no-op if metrics are recorded immediately.
        """


@fields.ClassConfigurationSchema.provider(fields.Dictionary(
    {},
    allow_extra_keys=True,
    description='The no-ops recorder has no constructor arguments',
))
class NoOpMetricsRecorder(MetricsRecorder):
    """
    A dummy metrics recorder that doesn't actually record any metrics and has no overhead, used when no
    metrics-recording settings have been configured.
    """
    class NoOpCounter(Counter):
        def increment(self, amount=1):
            """
            Does nothing.
            :param amount: Unused
            """

    class NoOpTimer(Timer):
        def start(self):
            """
            Does nothing.
            """

        def stop(self):
            """
            Does nothing.
            """

    no_op_counter = NoOpCounter()
    no_op_timer = NoOpTimer()

    def __init__(self, *_, **__):
        """
        A dummy constructor that ignores all arguments
        """

    def counter(self, name, **kwargs):
        """
        Returns a counter that does nothing.

        :param name: Unused

        :return: A do-nothing counter
        :rtype: NoOpMetricsRecorder.NoOpCounter
        """
        return self.no_op_counter

    def timer(self, name, **kwargs):
        """
        Returns a timer that does nothing.

        :param name: Unused

        :return: A do-nothing timer
        :rtype: NoOpMetricsRecorder.NoOpTimer
        """
        return self.no_op_timer

    def commit(self):
        """
        Does nothing
        """


class MetricsSchema(fields.ClassConfigurationSchema):
    base_class = MetricsRecorder
    description = 'Configuration for defining a usage and performance metrics recorder.'
