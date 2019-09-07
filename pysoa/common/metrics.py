from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc
import enum
from typing import (  # noqa: F401 TODO Python 3
    Any,
    Optional,
    Union,
)

from conformity import fields
import six


@six.add_metaclass(abc.ABCMeta)
class Counter(object):
    """
    Defines an interface for incrementing a counter.
    """

    @abc.abstractmethod
    def increment(self, amount=1):  # type: (int) -> None
        """
        Increments the counter.

        :param amount: The amount by which to increment the counter, which must default to 1.
        """


@six.add_metaclass(abc.ABCMeta)
class Histogram(object):
    """
    Defines an interface for tracking an arbitrary number of something per named activity.
    """

    @abc.abstractmethod
    def set(self, value=None):  # type: (Optional[Union[int, float]]) -> None
        """
        Sets the histogram value.

        :param value: The histogram value.
        """


class TimerResolution(enum.IntEnum):
    MILLISECONDS = 10**3
    MICROSECONDS = 10**6
    NANOSECONDS = 10**9


@six.add_metaclass(abc.ABCMeta)
class Timer(Histogram):
    """
    Defines an interface for timing activity. Can be used as a context manager to time wrapped activity. Exists as a
    special Histogram whose value can be set based on starting and stopping the timer.
    """

    @abc.abstractmethod
    def start(self):  # type: () -> None
        """
        Starts the timer.
        """

    @abc.abstractmethod
    def stop(self):  # type: () -> None
        """
        Stops the timer.
        """

    def __enter__(self):  # type: () -> Timer
        """
        Starts the timer at the start of the context manager. Returns self.
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):  # type: (Any, Any, Any) -> bool
        """
        Stops the timer at the end of the context manager. All parameters are ignored. Always returns ``False``.

        :return: ``False``
        """
        self.stop()
        return False


@six.add_metaclass(abc.ABCMeta)
class MetricsRecorder(object):
    """
    Defines an interface for recording metrics. All metrics recorders registered with PySOA must implement this
    interface. Note that counters and timers with the same name may not be recorded. If your metrics backend needs
    timers to also have associated counters, your implementation of this recorder must take care of filling that gap.
    """

    @abc.abstractmethod
    def counter(self, name, **kwargs):  # type: (six.text_type, Any) -> Counter
        """
        Returns a counter that can be incremented.

        :param name: The name of the counter
        :param kwargs: Any other arguments that may be needed (unrecognized keyword arguments should be treated as
                       metric "tags" and either passed to the metrics backend, if supported, or ignored)

        :return: a counter object.
        """

    @abc.abstractmethod
    def histogram(self, name, **kwargs):  # type: (six.text_type, Any) -> Histogram
        """
        Returns a histogram that can be set.

        :param name: The name of the histogram
        :param kwargs: Any other arguments that may be needed (unrecognized keyword arguments should be treated as
                       metric "tags" and either passed to the metrics backend, if supported, or ignored)

        :return: a histogram object.
        """

    @abc.abstractmethod
    def timer(self, name, resolution=TimerResolution.MILLISECONDS, **kwargs):
        # type: (six.text_type, TimerResolution, Any) -> Timer
        """
        Returns a timer that can be started and stopped.

        :param name: The name of the timer
        :param resolution: The resolution at which this timer should operate, defaulting to milliseconds. Its value
                           should be a `TimerResolution` or any other equivalent `IntEnum` whose values serve as
                           integer multipliers to convert decimal seconds to the corresponding units. It will only
                           ever be access as a keyword argument, never as a positional argument, so it is not necessary
                           for this to be the second positional argument in your equivalent recorder class.
        :type resolution: enum.IntEnum
        :param kwargs: Any other arguments that may be needed (unrecognized keyword arguments should be treated as
                       metric "tags" and either passed to the metrics backend, if supported, or ignored)

        :return: a timer object.
        """

    def commit(self):  # type: () -> None
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
        def increment(self, amount=1):  # type: (int) -> None
            """
            Does nothing.
            :param amount: Unused
            """

    class NoOpHistogram(Histogram):
        def set(self, value=None):  # type: (Optional[Union[int, float]]) -> None
            """
            Does nothing.
            :param value: Unused
            """

    class NoOpTimer(Timer, NoOpHistogram):
        def start(self):  # type: () -> None
            """
            Does nothing.
            """

        def stop(self):  # type: () -> None
            """
            Does nothing.
            """

    no_op_counter = NoOpCounter()
    no_op_histogram = NoOpHistogram()
    no_op_timer = NoOpTimer()

    def __init__(self, *_, **__):  # type: (Any, Any) -> None
        """
        A dummy constructor that ignores all arguments
        """

    def counter(self, name, **kwargs):  # type: (six.text_type, Any) -> Counter
        """
        Returns a counter that does nothing.

        :param name: Unused

        :return: A do-nothing counter
        """
        return self.no_op_counter

    def histogram(self, name, **kwargs):  # type: (six.text_type, Any) -> Histogram
        """
        Returns a histogram that does nothing.

        :param name: Unused

        :return: A do-nothing histogram
        """
        return self.no_op_histogram

    def timer(self, name, resolution=TimerResolution.MILLISECONDS, **kwargs):
        # type: (six.text_type, TimerResolution, Any) -> Timer
        """
        Returns a timer that does nothing.

        :param name: Unused
        :param resolution: Unused

        :return: A do-nothing timer
        """
        return self.no_op_timer

    def commit(self):
        # type: () -> None
        """
        Does nothing
        """


class MetricsSchema(fields.ClassConfigurationSchema):
    base_class = MetricsRecorder
    description = 'Configuration for defining a usage and performance metrics recorder.'
