from __future__ import unicode_literals

from unittest import TestCase

from pysoa.client.client import Client


class TestClientWithExpansions(TestCase):

    def setUp(self):
        expansion_config = {
            'type_routes': {
                'author_router': {
                    'service': 'author_info_service',
                    'action': 'get_authors_by_ids',
                    'request_field': 'ids',
                    'response_field': 'authors_detail',
                },
                'publisher_type': {  # Note: Likely a bug here
                    'service': 'publisher_info_service',
                    'action': 'get_publishers_by_ids',
                    'request_field': 'ids',
                    'response_field': 'publishers_detail',
                },
                'address_router': {
                    'service': 'address_info_service',
                    'action': 'get_addresses_by_ids',
                    'request_field': 'ids',
                    'response_field': 'addresses_detail',
                },
                'automaker_router': {
                    'service': 'automaker_info_service',
                    'action': 'get_automakers_by_ids',
                    'request_field': 'ids',
                    'response_field': 'automakers_detail',
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
            'get_authors_by_ids': {
                'body': {
                    'authors_detail': {
                        '2': {
                            '_type': 'author_type',
                            'id': 2,
                            'stuff': 'things',
                        },
                    }
                }
            }
        }

        publisher_transport_action_map = {
            'get_publishers_by_ids': {
                'body': {
                    'publishers_detail': {
                        '3': {
                            '_type': 'publisher_type',
                            'id': 3,
                            'address_id': 4,
                        },
                    }
                }
            }
        }

        address_transport_action_map = {
            'get_addresses_by_ids': {
                'body': {
                    'addresses_detail': {
                        '4': {
                            '_type': 'address_type',
                            'id': 4,
                        },
                    }
                }
            }
        }

        automaker_transport_action_map = {
            'get_automakers_by_ids': {
                'body': {
                    'automakers_detail': {
                        '6': {
                            '_type': 'auto_type',
                            'id': 6,
                        },
                    }
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
                'author_id': 2,
                'publish_id': 3,
                'author_profile': {
                    '_type': 'author_type',
                    'id': 2,
                    'stuff': 'things',
                },
                'publisher_profile': {
                    '_type': 'publisher_type',
                    'id': 3,
                    'address_id': 4,
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
                'automaker_id': 6,
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

    def test_call_actions_parallel_with_expansions(self):
        expected_book_response = {
            'book_obj': {
                '_type': 'book_type',
                'id': 1,
                'author_id': 2,
                'publish_id': 3,
                'author_profile': {
                    '_type': 'author_type',
                    'id': 2,
                    'stuff': 'things',
                },
                'publisher_profile': {
                    '_type': 'publisher_type',
                    'id': 3,
                    'address_id': 4,
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
                'automaker_id': 6,
                'automaker_profile': {
                    '_type': 'auto_type',
                    'id': 6,
                },
            },
        }

        actions = self.client.call_actions_parallel(
            service_name='book_info_service',
            actions=[
                {'action': 'get_book', 'body': {'id': 1}},
                {'action': 'get_car', 'body': {'id': 5}},
            ],
            expansions={
                'book_type': ['author_rule', 'publisher_rule.address_rule'],
                'car_type': ['automaker_rule'],
            },
        )

        actions = list(actions)
        self.assertEqual(2, len(actions))
        self.assertEqual(expected_book_response, actions[0].body)
        self.assertEqual(expected_car_response, actions[1].body)

    def test_call_jobs_parallel_with_expansions(self):
        expected_book_response = {
            'book_obj': {
                '_type': 'book_type',
                'id': 1,
                'author_id': 2,
                'publish_id': 3,
                'author_profile': {
                    '_type': 'author_type',
                    'id': 2,
                    'stuff': 'things',
                },
                'publisher_profile': {
                    '_type': 'publisher_type',
                    'id': 3,
                    'address_id': 4,
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
                'automaker_id': 6,
                'automaker_profile': {
                    '_type': 'auto_type',
                    'id': 6,
                },
            },
        }

        job_responses = self.client.call_jobs_parallel(
            jobs=[
                {'service_name': 'book_info_service', 'actions': [{'action': 'get_book', 'body': {'id': 1}}]},
                {'service_name': 'book_info_service', 'actions': [{'action': 'get_car', 'body': {'id': 5}}]},
            ],
            expansions={
                'book_type': ['author_rule', 'publisher_rule.address_rule'],
                'car_type': ['automaker_rule'],
            },
        )

        self.assertEqual(2, len(job_responses))
        self.assertEqual(expected_book_response, job_responses[0].actions[0].body)
        self.assertEqual(expected_car_response, job_responses[1].actions[0].body)

    def test_call_action_with_expansions(self):
        expected_response = {
            'book_obj': {
                '_type': 'book_type',
                'id': 1,
                'author_id': 2,
                'publish_id': 3,
                'author_profile': {
                    '_type': 'author_type',
                    'id': 2,
                    'stuff': 'things',
                },
                'publisher_profile': {
                    '_type': 'publisher_type',
                    'id': 3,
                    'address_id': 4,
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
        errors = [{
            'code': 'INVALID',
            'field': 'id',
            'message': 'Invalid author ID',
        }]
        self.client._get_handler('author_info_service').transport.stub_action('get_authors_by_ids', errors=errors)
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
        self.client._get_handler('publisher_info_service').transport.stub_action('get_publishers_by_ids', errors=errors)

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

    def test_expansion_client_key_error(self):
        errors = [{
            'code': 'INVALID',
            'field': 'id',
            'message': 'Invalid author ID',
        }]
        self.client._get_handler('author_info_service').transport.stub_action('get_authors_by_ids', errors=errors)

        with self.assertRaises(self.client.InvalidExpansionKey) as err:
            self.client.call_action(
                service_name='book_info_service',
                action='get_book',
                body={
                    'id': 1,
                },
                expansions={
                    'book_type': ['author_rule_typo_key'],
                },
            )
        message, = err.exception.args
        self.assertEqual(message, 'Invalid key in expansion request: author_rule_typo_key')
