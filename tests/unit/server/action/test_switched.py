from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Callable,
    Optional,
    SupportsInt,
    cast,
)
import unittest

from conformity import fields

from pysoa.common.errors import Error
from pysoa.common.types import ActionResponse
from pysoa.server.action.base import Action
from pysoa.server.action.switched import SwitchedAction
from pysoa.server.errors import ActionError
from pysoa.server.internal.types import (
    get_switch,
    is_switch,
)
from pysoa.server.settings import ServerSettings
from pysoa.server.types import EnrichedActionRequest


class SwitchTwelve(object):
    def __int__(self):
        return 12


class ValueSwitch(object):
    def __init__(self, value):  # type: (SupportsInt) -> None
        self.value = value


class ActionOne(Action):
    request_schema = fields.Dictionary({'planet': fields.UnicodeString()})

    response_schema = fields.Dictionary({'planet_response': fields.UnicodeString(), 'settings': fields.Anything()})

    def run(self, request):
        return {'planet_response': request.body['planet'], 'settings': self.settings}


def action_two(settings):  # type: (Optional[ServerSettings]) -> Callable[[EnrichedActionRequest], ActionResponse]
    def action_logic(request):  # type: (EnrichedActionRequest) -> ActionResponse
        return ActionResponse(action='one', body={'animal_response': request.body['animal'], 'settings': settings})
    return action_logic


def action_three(_):  # type: (Optional[ServerSettings]) -> Callable[[EnrichedActionRequest], ActionResponse]
    def action_logic(request):  # type: (EnrichedActionRequest) -> ActionResponse
        return ActionResponse(action='one', body={'building_response': request.body['building']})
    return action_logic


class SwitchedActionOne(SwitchedAction):
    switch_to_action_map = (
        (SwitchTwelve(), ActionOne),
        (5, action_two),
    )


class SwitchedActionTwo(SwitchedAction):
    switch_to_action_map = (
        (SwitchedAction.DEFAULT_ACTION, action_three),
        (ValueSwitch(7), action_two),
        (ValueSwitch(SwitchTwelve()), ActionOne),
    )


class TestSwitchedAction(unittest.TestCase):
    def test_action_one_switch_twelve(self):
        settings = {'foo': 'bar'}

        action = SwitchedActionOne(cast(ServerSettings, settings))

        response = action(EnrichedActionRequest(action='one', body={'planet': 'Mars'}, switches=[12]))

        self.assertEqual([], response.errors)
        self.assertEqual({'planet_response': 'Mars', 'settings': settings}, response.body)

    def test_action_one_switches_twelve_and_five(self):
        settings = {'baz': 'qux'}

        action = SwitchedActionOne(cast(ServerSettings, settings))

        response = action(EnrichedActionRequest(action='one', body={'planet': 'Jupiter'}, switches=[12, 5]))

        self.assertEqual([], response.errors)
        self.assertEqual({'planet_response': 'Jupiter', 'settings': settings}, response.body)

    def test_action_one_switch_five(self):
        settings = {'foo': 'bar'}

        action = SwitchedActionOne(cast(ServerSettings, settings))

        response = action(EnrichedActionRequest(action='one', body={'animal': 'cat'}, switches=[5]))

        self.assertEqual([], response.errors)
        self.assertEqual({'animal_response': 'cat', 'settings': settings}, response.body)

    def test_action_no_switches(self):
        settings = {'foo': 'bar'}

        action = SwitchedActionOne(cast(ServerSettings, settings))

        response = action(EnrichedActionRequest(action='one', body={'animal': 'cat'}, switches=[]))

        self.assertEqual([], response.errors)
        self.assertEqual({'animal_response': 'cat', 'settings': settings}, response.body)

    def test_action_one_switch_twelve_with_errors(self):
        settings = {'foo': 'bar'}

        action = SwitchedActionOne(cast(ServerSettings, settings))

        with self.assertRaises(ActionError) as error_context:
            action(EnrichedActionRequest(action='one', body={'animal': 'cat'}, switches=[12]))

        self.assertEqual(2, len(error_context.exception.errors))
        self.assertIn(
            Error('MISSING', 'Missing key: planet', field='planet', is_caller_error=True),
            error_context.exception.errors,
        )
        self.assertIn(
            Error('UNKNOWN', 'Extra keys present: animal', is_caller_error=True),
            error_context.exception.errors,
        )

    def test_action_two_switch_seven(self):
        settings = {'baz': 'qux'}

        action = SwitchedActionTwo(cast(ServerSettings, settings))

        response = action(EnrichedActionRequest(action='one', body={'animal': 'dog'}, switches=[7]))

        self.assertEqual([], response.errors)
        self.assertEqual({'animal_response': 'dog', 'settings': settings}, response.body)

    def test_action_two_switch_twelve(self):
        settings = {'foo': 'bar'}

        action = SwitchedActionTwo(cast(ServerSettings, settings))

        response = action(EnrichedActionRequest(action='one', body={'planet': 'Pluto'}, switches=[12]))

        self.assertEqual([], response.errors)
        self.assertEqual({'planet_response': 'Pluto', 'settings': settings}, response.body)

    def test_action_two_no_switches(self):
        settings = {'foo': 'bar'}

        action = SwitchedActionTwo(cast(ServerSettings, settings))

        response = action(EnrichedActionRequest(
            action='one',
            body={'building': 'Empire State Building'},
            switches=[],
        ))

        self.assertEqual([], response.errors)
        self.assertEqual({'building_response': 'Empire State Building'}, response.body)


class TestSwitchedActionValidation(unittest.TestCase):
    def test_cannot_instantiate_base(self):
        with self.assertRaises(TypeError) as error_context:
            SwitchedAction(cast(ServerSettings, {}))

        self.assertIn('instantiate', error_context.exception.args[0])

    def test_map_is_none(self):
        with self.assertRaises(ValueError) as error_context:
            # noinspection PyUnusedLocal
            class BadAction(SwitchedAction):
                switch_to_action_map = None  # type: ignore

        self.assertIn('switch_to_action_map', error_context.exception.args[0])

    def test_map_is_not_iterable(self):
        with self.assertRaises(ValueError) as error_context:
            # noinspection PyUnusedLocal
            class BadAction(SwitchedAction):
                switch_to_action_map = 7  # type: ignore

        self.assertIn('switch_to_action_map', error_context.exception.args[0])

    def test_map_is_iterable_but_has_no_length(self):
        with self.assertRaises(ValueError) as error_context:
            # noinspection PyUnusedLocal
            class BadAction(SwitchedAction):
                switch_to_action_map = (x for x in range(10))  # type: ignore

        self.assertIn('switch_to_action_map', error_context.exception.args[0])

    def test_map_is_empty(self):
        with self.assertRaises(ValueError) as error_context:
            # noinspection PyUnusedLocal
            class BadAction(SwitchedAction):
                switch_to_action_map = ()

        self.assertIn('switch_to_action_map', error_context.exception.args[0])

    def test_map_has_only_one_valid_item(self):
        with self.assertRaises(ValueError) as error_context:
            # noinspection PyUnusedLocal
            class BadAction(SwitchedAction):
                switch_to_action_map = ((5, ActionOne), )

        self.assertIn('switch_to_action_map', error_context.exception.args[0])

    def test_map_has_multiple_items_but_one_is_invalid_switch(self):
        with self.assertRaises(ValueError) as error_context:
            # noinspection PyUnusedLocal
            class BadAction(SwitchedAction):
                switch_to_action_map = (
                    (5, ActionOne),  # type: ignore
                    (TestSwitchedActionValidation, action_two),  # type: ignore
                )

        self.assertIn('switch_to_action_map', error_context.exception.args[0])

    def test_map_has_multiple_items_but_one_is_invalid_action(self):
        with self.assertRaises(ValueError) as error_context:
            # noinspection PyUnusedLocal
            class BadAction(SwitchedAction):
                switch_to_action_map = (
                    (5, ActionOne),  # type: ignore
                    (0, 7),  # type: ignore
                )

        self.assertIn('switch_to_action_map', error_context.exception.args[0])


class TestSwitchHelpers(unittest.TestCase):
    def test_is_switch(self):
        self.assertTrue(is_switch(5))
        self.assertTrue(is_switch(12348798123498798987919872349879879123498713249161234987134987))
        self.assertTrue(is_switch(SwitchTwelve()))
        self.assertTrue(is_switch(ValueSwitch(31)))
        self.assertTrue(is_switch(ValueSwitch(SwitchTwelve())))
        self.assertFalse(is_switch('hello'))
        self.assertFalse(is_switch(Exception()))
        self.assertFalse(is_switch(ActionOne(cast(ServerSettings, {}))))

    def test_get_switch(self):
        self.assertEqual(5, get_switch(5))
        self.assertEqual(
            12348798123498798987919872349879879123498713249161234987134987,
            get_switch(12348798123498798987919872349879879123498713249161234987134987),
        )
        self.assertEqual(12, get_switch(SwitchTwelve()))
        self.assertEqual(31, get_switch(ValueSwitch(31)))
        self.assertEqual(12, get_switch(ValueSwitch(SwitchTwelve())))

        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            get_switch('hello')  # type: ignore

        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            get_switch(Exception())  # type: ignore

        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            get_switch(ActionOne({}))  # type: ignore
