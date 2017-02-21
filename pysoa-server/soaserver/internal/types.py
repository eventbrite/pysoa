import six


class SwitchSet(frozenset):
    """Immutable set subtype for interacting with switches"""

    def __new__(cls, switches=[]):
        """Create a new SwitchSet instance

        Args:
            switches: an iterable of integers or objects that implement the
                switch constant interface.
        Returns:
            a new SwitchSet.
        Raises:
            TypeError: if switches is not an iterable or if a switch object does
                not implement the switch constant interface.
        """

        return super(SwitchSet, cls).__new__(
            cls,
            cls._process_switches(switches),
        )

    def __contains__(self, switch):
        """Determine whether or not a switch is in the SwitchSet

        Args:
            switch: an integer or object that implements the switch constant
                interface.
        Returns:
            a boolean indicating whether or not the switch is active
            (i.e. in the set)
        Raises:
            TypeError: if switch does not implement the switch constant
                interface.
        """

        if isinstance(switch, six.integer_types):
            return super(SwitchSet, self).__contains__(switch)
        elif isinstance(getattr(switch, 'value', None), int):
            return super(SwitchSet, self).__contains__(switch.value)
        else:
            raise TypeError(
                'switch does not implement the switch constant interface'
            )

    @staticmethod
    def _process_switches(switches):
        for switch in switches:
            if isinstance(switch, six.integer_types):
                yield switch
            elif isinstance(getattr(switch, 'value', None), int):
                yield switch.value
            else:
                raise TypeError(
                    'switch does not implement the switch constant interface'
                )


class RequestSwitchSet(SwitchSet):
    def is_active(self, switch):
        """Determine whether or not a switch is active

        Args:
            switch: an integer or object that implements the switch constant
                interface.
        Returns:
            a boolean indicating whether or not the switch is active
            (i.e. in the set)
        Raises:
            TypeError: if switch does not implement the switch constant
                interface.
        """

        return switch in self
