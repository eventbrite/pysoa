from __future__ import unicode_literals

from conformity import fields

from pysoa.common.schemas import BasicClassSchema


class Counter(object):
    """
    Defines an interface for incrementing a counter.
    """

    def increment(self, amount=1):
        """
        Increments the counter.

        :param amount: The amount by which to increment the counter, which must default to 1.
        """
        raise NotImplementedError()


class Timer(object):
    """
    Defines an interface for timing activity. Can be used as a context manager to time wrapped activity.
    """

    def start(self):
        """
        Starts the timer.
        """
        raise NotImplementedError()

    def stop(self):
        """
        Stops the timer.
        """
        raise NotImplementedError()

    def __enter__(self):
        self.start()

    def __exit__(self, *_, **__):
        self.stop()
        return False


class MetricsRecorder(object):
    """
    Defines an interface for recording metrics. All metrics recorders registered with PySOA must implement this
    interface. Note that counters and timers with the same name will not be recorded. If your metrics backend needs
    timers to also have associated counters, your implementation of this recorder must take care of filling that gap.
    """

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

    def timer(self, name, **kwargs):
        """
        Returns a timer that can be started and stopped. Implementations do not have to return an instance of `Timer`,
        but they must at least return an object that matches the interface for `Timer`, including serving as a context
        manager.

        :param name: The name of the timer
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


class NoOpMetricsRecorder(MetricsRecorder):
    class NoOpCounter(Counter):
        def increment(self, amount=1):
            pass

    class NoOpTimer(Timer):
        def start(self):
            pass

        def stop(self):
            pass

    _counter = NoOpCounter()
    _timer = NoOpTimer()

    def __init__(self, **__):
        pass

    def counter(self, name, **kwargs):
        return self._counter

    def timer(self, name, **kwargs):
        return self._timer

    def commit(self):
        pass


class MetricsSchema(BasicClassSchema):
    contents = {
        'path': fields.UnicodeString(description='The module.name:ClassName path to the metrics recorder'),
        'kwargs': fields.Dictionary(
            {
                'config': fields.SchemalessDictionary(),
            },
            optional_keys=[
                'config',
            ],
            allow_extra_keys=True,
            description='The keyword arguments that will be passed to the constructed metrics recorder',
        ),
    }

    object_type = MetricsRecorder
