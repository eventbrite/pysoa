from __future__ import unicode_literals

from unittest import TestCase

from pysoa.client.client import Client


class TestClientWithExpansions(TestCase):

    def setUp(self):
        expansion_config = {
            'type_routes': {
                'author_router': {
                    'service': 'author_info_service',
                    'action': 'get_author_by_id',
                    'request_field': 'id',
                    'response_field': 'author_detail',
                },
                'publisher_type': {  # Note: Likely a bug here
                    'service': 'publisher_info_service',
                    'action': 'get_publisher_by_id',
                    'request_field': 'id',
                    'response_field': 'publisher_detail',
                },
                'address_router': {
                    'service': 'address_info_service',
                    'action': 'get_address_by_id',
                    'request_field': 'id',
                    'response_field': 'address_detail',
                },
                'automaker_router': {
                    'service': 'automaker_info_service',
                    'action': 'get_automaker_by_id',
                    'request_field': 'id',
                    'response_field': 'automaker_detail',
                },
            },
            'type_expansions': {
                'book_type': {
                    'author_rule': {
                        'type': 'author_router',
                        'source_field': 'author_id',
                        'dest_field': 'author_profile',
                    },
                    'publisher_rule': {
                        'type': 'publisher_type',
                        'source_field': 'publish_id',
                        'dest_field': 'publisher_profile',
                        'raise_action_errors': True,
                    },
                },
                'publisher_type': {
                    'address_rule': {
                        'type': 'address_router',
                        'source_field': 'address_id',
                        'dest_field': 'address_profile',
                    },
                },
                'car_type': {
                    'automaker_rule': {
                        'type': 'automaker_router',
                        'source_field': 'automaker_id',
                        'dest_field': 'automaker_profile',
                    },
                },
            },
        }
        book_transport_action_map = {
            'get_book': {
                'body': {
                    'book_obj': {
                        '_type': 'book_type',
                        'id': 1,
                        'author_id': 2,
                        'publish_id': 3,
                    },
                },
            },
            'get_car': {
                'body': {
                    'car_obj': {
                        '_type': 'car_type',
                        'id': 5,
                        'automaker_id': 6,
                    },
                }
            }
        }

        author_transport_action_map = {
            'get_author_by_id': {
                'body': {
                    'author_detail': {
                        '_type': 'author_type',
                        'id': 2,
                        'stuff': 'things',
                    },
                }
            }
        }

        publisher_transport_action_map = {
            'get_publisher_by_id': {
                'body': {
                    'publisher_detail': {
                        '_type': 'publisher_type',
                        'id': 3,
                        'address_id': 4,
                    },
                }
            }
        }

        address_transport_action_map = {
            'get_address_by_id': {
                'body': {
                    'address_detail': {
                        '_type': 'address_type',
                        'id': 4,
                    },
                }
            }
        }

        automaker_transport_action_map = {
            'get_automaker_by_id': {
                'body': {
                    'automaker_detail': {
                        '_type': 'auto_type',
                        'id': 6,
                    },
                }
            }
        }

        config = {
            'book_info_service': {
                'transport': {
                    'path': 'pysoa.test.stub_service:StubClientTransport',
                    'kwargs': {
                        'action_map': book_transport_action_map,
                    }
                }
            },
            'author_info_service': {
                'transport': {
                    'path': 'pysoa.test.stub_service:StubClientTransport',
                    'kwargs': {
                        'action_map': author_transport_action_map,
                    }
                }
            },
            'publisher_info_service': {
                'transport': {
                    'path': 'pysoa.test.stub_service:StubClientTransport',
                    'kwargs': {
                        'action_map': publisher_transport_action_map,
                    }
                }
            },
            'address_info_service': {
                'transport': {
                    'path': 'pysoa.test.stub_service:StubClientTransport',
                    'kwargs': {
                        'action_map': address_transport_action_map,
                    }
                }
            },
            'automaker_info_service': {
                'transport': {
                    'path': 'pysoa.test.stub_service:StubClientTransport',
                    'kwargs': {
                        'action_map': automaker_transport_action_map,
                    }
                }
            },
        }

        self.client = Client(config=config, expansion_config=expansion_config)

    def test_call_actions_with_expansions(self):
        expected_book_response = {
            'book_obj': {
                '_type': 'book_type',
                'id': 1,
                'author_profile': {
                    '_type': 'author_type',
                    'id': 2,
                    'stuff': 'things',
                },
                'publisher_profile': {
                    '_type': 'publisher_type',
                    'id': 3,
                    'address_profile': {
                        '_type': 'address_type',
                        'id': 4,
                    },
                },
            },
        }
        expected_car_response = {
            'car_obj': {
                '_type': 'car_type',
                'id': 5,
                'automaker_profile': {
                    '_type': 'auto_type',
                    'id': 6,
                },
            },
        }

        response = self.client.call_actions(
            service_name='book_info_service',
            actions=[
                {
                    'action': 'get_book',
                    'body': {
                        'id': 1,
                    },
                },
                {
                    'action': 'get_car',
                    'body': {
                        'id': 5,
                    }
                },
            ],
            expansions={
                'book_type': ['author_rule', 'publisher_rule.address_rule'],
                'car_type': ['automaker_rule'],
            },
        )

        self.assertEqual(
            response.actions[0].body,
            expected_book_response,
        )

        self.assertEqual(
            response.actions[1].body,
            expected_car_response,
        )

    def test_call_action_with_expansions(self):
        expected_response = {
            'book_obj': {
                '_type': 'book_type',
                'id': 1,
                'author_profile': {
                    '_type': 'author_type',
                    'id': 2,
                    'stuff': 'things',
                },
                'publisher_profile': {
                    '_type': 'publisher_type',
                    'id': 3,
                    'address_profile': {
                        '_type': 'address_type',
                        'id': 4,
                    },
                },
            },
        }

        response = self.client.call_action(
            service_name='book_info_service',
            action='get_book',
            body={
                'id': 1,
            },
            expansions={
                'book_type': ['author_rule', 'publisher_rule.address_rule'],
            },
        )

        self.assertEqual(
            response.body,
            expected_response,
        )

    def test_expansion_fail_silently(self):
        author_errors = [{
            'code': 'INVALID',
            'field': 'id',
            'message': 'Invalid author ID',
        }]
        self.client._get_handler('author_info_service').transport.stub_action('get_author_by_id', errors=author_errors)
        expected_response = {
            'book_obj': {
                '_type': 'book_type',
                'id': 1,
                'author_id': 2,
                'publish_id': 3,
            },
        }
        response = self.client.call_action(
            service_name='book_info_service',
            action='get_book',
            body={
                'id': 1,
            },
            expansions={
                'book_type': ['author_rule'],
            },
        )
        self.assertEqual(response.body, expected_response)

    def test_expansion_error_raises_exception(self):
        errors = [{
            'code': 'INVALID',
            'field': 'id',
            'message': 'Invalid publisher ID',
        }]
        self.client._get_handler('publisher_info_service').transport.stub_action('get_publisher_by_id', errors=errors)

        with self.assertRaises(self.client.CallActionError) as e:
            self.client.call_action(
                service_name='book_info_service',
                action='get_book',
                body={
                    'id': 1,
                },
                expansions={
                    'book_type': ['publisher_rule'],
                },
            )
        err = e.exception.actions[0].errors[0]
        self.assertEqual(err.code, 'INVALID')
        self.assertEqual(err.field, 'id')
        self.assertEqual(err.message, 'Invalid publisher ID')
