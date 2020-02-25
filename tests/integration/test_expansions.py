from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import cast
from unittest import TestCase

from pysoa.client.client import Client
from pysoa.test.compatibility import mock
from pysoa.test.stub_service import (
    StubClientTransport,
    stub_action,
)


class TestClientWithExpansions(TestCase):

    def setUp(self):
        expansion_config = {
            'type_routes': {
                'author_route': {
                    'service': 'author_info_service',
                    'action': 'get_authors_by_ids',
                    'request_field': 'ids',
                    'response_field': 'authors_detail',
                },
                'publisher_route': {  # Note: Likely a bug here
                    'service': 'publisher_info_service',
                    'action': 'get_publishers_by_ids',
                    'request_field': 'ids',
                    'response_field': 'publishers_detail',
                },
                'address_route': {
                    'service': 'address_info_service',
                    'action': 'get_addresses_by_ids',
                    'request_field': 'ids',
                    'response_field': 'addresses_detail',
                },
                'automaker_route': {
                    'service': 'automaker_info_service',
                    'action': 'get_automakers_by_ids',
                    'request_field': 'ids',
                    'response_field': 'automakers_detail',
                },
            },
            'type_expansions': {
                'book_type': {
                    'author_rule': {
                        'type': None,
                        'route': 'author_route',
                        'source_field': 'author_id',
                        'destination_field': 'author_profile',
                    },
                    'publisher_rule': {
                        'type': 'publisher_type',
                        'route': 'publisher_route',
                        'source_field': 'publish_id',
                        'destination_field': 'publisher_profile',
                        'raise_action_errors': True,
                    },
                },
                'publisher_type': {
                    'address_rule': {
                        'type': None,
                        'route': 'address_route',
                        'source_field': 'address_id',
                        'destination_field': 'address_profile',
                    },
                },
                'car_type': {
                    'automaker_rule': {
                        'type': None,
                        'route': 'automaker_route',
                        'source_field': 'automaker_id',
                        'destination_field': 'automaker_profile',
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
                        2: {
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
                        3: {
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
                        4: {
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
                        6: {
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

    def test_call_actions_with_expansions_and_stubbed_initial_call(self):
        expected_book_response = {
            'book_obj': {
                '_type': 'book_type',
                'id': 10573,
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

        with stub_action('book_info_service', 'get_book', body={'book_obj': {
            '_type': 'book_type',
            'id': 10573,
            'author_id': 2,
            'publish_id': 3,
        }}):
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

    def test_call_actions_with_expansions_and_stubbed_expansion_call(self):
        expected_book_response = {
            'book_obj': {
                '_type': 'book_type',
                'id': 1,
                'author_id': 2,
                'publish_id': 3,
                'author_profile': {
                    '_type': 'author_type',
                    'id': 201838,
                    'things': 'stuff',
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

        with stub_action('author_info_service', 'get_authors_by_ids', body={'authors_detail': {
            2: {
                '_type': 'author_type',
                'id': 201838,
                'things': 'stuff',
            },
        }}):
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

    def test_call_actions_with_expansions_and_stubbed_initial_and_expansion_calls(self):
        expected_book_response = {
            'book_obj': {
                '_type': 'book_type',
                'id': 10573,
                'author_id': 2,
                'publish_id': 3,
                'author_profile': {
                    '_type': 'author_type',
                    'id': 201838,
                    'things': 'stuff',
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

        with stub_action('author_info_service', 'get_authors_by_ids', body={'authors_detail': {
            2: {
                '_type': 'author_type',
                'id': 201838,
                'things': 'stuff',
            },
        }}), \
                stub_action('book_info_service', 'get_book', body={'book_obj': {
                    '_type': 'book_type',
                    'id': 10573,
                    'author_id': 2,
                    'publish_id': 3,
                }}):
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

        actions_list = list(actions)
        self.assertEqual(2, len(actions_list))
        self.assertEqual(expected_book_response, actions_list[0].body)
        self.assertEqual(expected_car_response, actions_list[1].body)

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
        cast(
            StubClientTransport,
            self.client._get_handler('author_info_service').transport,
        ).stub_action('get_authors_by_ids', errors=errors)
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
        cast(
            StubClientTransport,
            self.client._get_handler('publisher_info_service').transport,
        ).stub_action('get_publishers_by_ids', errors=errors)

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
        cast(
            StubClientTransport,
            self.client._get_handler('author_info_service').transport,
        ).stub_action('get_authors_by_ids', errors=errors)

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


class AnyOrderEqualsList(list):
    def __eq__(self, other):
        return isinstance(other, list) and len(other) == len(self) and set(other) == set(self)


class TestComplexCompanyHierarchyExpansions(TestCase):
    maxDiff = 6000

    def setUp(self):
        expansion_config = {
            'type_routes': {
                'employee_route': {
                    'service': 'employee_service',
                    'action': 'get_employees_by_ids',
                    'request_field': 'employee_ids',
                    'response_field': 'employees',
                },
                'employee_report_route': {
                    'service': 'employee_service',
                    'action': 'get_employees_reports_by_manager_ids',
                    'request_field': 'manager_ids',
                    'response_field': 'reports',
                },
                'company_employees_route': {
                    'service': 'employee_service',
                    'action': 'get_company_employees_by_company_ids',
                    'request_field': 'company_ids',
                    'response_field': 'employees',
                },
                'image_route': {
                    'service': 'image_service',
                    'action': 'get_images_by_ids',
                    'request_field': 'image_ids',
                    'response_field': 'images',
                },
            },
            'type_expansions': {
                'company_type': {
                    'ceo': {
                        'type': 'employee_type',
                        'route': 'employee_route',
                        'source_field': 'ceo_id',
                        'destination_field': 'ceo',
                    },
                    'logo': {
                        'type': None,
                        'route': 'image_route',
                        'source_field': 'logo_id',
                        'destination_field': 'logo',
                    },
                    'employees': {
                        'type': 'employee_type',
                        'route': 'company_employees_route',
                        'source_field': 'company_id',
                        'destination_field': 'employees'
                    }
                },
                'employee_type': {
                    'manager': {
                        'type': 'employee_type',
                        'route': 'employee_route',
                        'source_field': 'manager_id',
                        'destination_field': 'manager',
                    },
                    'photo': {
                        'type': None,
                        'route': 'image_route',
                        'source_field': 'photo_id',
                        'destination_field': 'photo',
                    },
                    'reports': {
                        'type': 'employee_type',
                        'route': 'employee_report_route',
                        'source_field': 'employee_id',
                        'destination_field': 'reports',
                    },
                },
            },
        }

        self.client = Client(config={}, expansion_config=expansion_config)

    @stub_action('image_service', 'get_images_by_ids')
    @stub_action('employee_service', 'get_employees_by_ids')
    @stub_action('company_service', 'get_all_companies')
    def test_expand_company_ceo_and_logo_nested_approach(self, mock_get_companies, mock_get_employees, mock_get_images):
        mock_get_companies.return_value = {
            'companies': [
                {'_type': 'company_type', 'company_id': '9183', 'name': 'Acme', 'ceo_id': '5791'},
                {'_type': 'company_type', 'company_id': '7261', 'name': 'Logo Makers', 'ceo_id': '51', 'logo_id': '65'},
            ],
        }

        mock_get_employees.return_value = {
            'employees': {
                '5791': {'_type': 'employee_type', 'employee_id': '5791', 'name': 'Julia', 'photo_id': '37'},
                '51': {'_type': 'employee_type', 'employee_id': '51', 'name': 'Nathan', 'photo_id': '79'},
            },
        }

        mock_get_images.side_effect = (
            {'images': {'65': {'image_id': '65', 'uri': '65.jpg'}}},
            {'images': {'37': {'image_id': '37', 'uri': '37.jpg'}, '79': {'image_id': '79', 'uri': '79.jpg'}}},
        )

        response = self.client.call_action(
            'company_service',
            'get_all_companies',
            body={},
            expansions={'company_type': ['ceo', 'ceo.photo', 'logo']},
        )

        mock_get_companies.assert_called_once_with({})
        mock_get_employees.assert_called_once_with({'employee_ids': AnyOrderEqualsList(['5791', '51'])})
        mock_get_images.assert_has_calls(
            [
                mock.call({'image_ids': ['65']}),
                mock.call({'image_ids': AnyOrderEqualsList(['37', '79'])}),
            ],
        )

        expected_response = {
            'companies': [
                {
                    '_type': 'company_type',
                    'company_id': '9183',
                    'name': 'Acme',
                    'ceo_id': '5791',
                    'ceo': {
                        '_type': 'employee_type',
                        'employee_id': '5791',
                        'name': 'Julia',
                        'photo_id': '37',
                        'photo': {'image_id': '37', 'uri': '37.jpg'},
                    },
                },
                {
                    '_type': 'company_type',
                    'company_id': '7261',
                    'name': 'Logo Makers',
                    'ceo_id': '51',
                    'ceo': {
                        '_type': 'employee_type',
                        'employee_id': '51',
                        'name': 'Nathan',
                        'photo_id': '79',
                        'photo': {'image_id': '79', 'uri': '79.jpg'},
                    },
                    'logo_id': '65',
                    'logo': {'image_id': '65', 'uri': '65.jpg'},
                },
            ],
        }

        self.assertEqual(expected_response, response.body)

    @stub_action('image_service', 'get_images_by_ids')
    @stub_action('employee_service', 'get_employees_by_ids')
    @stub_action('company_service', 'get_all_companies')
    def test_expand_company_ceo_and_logo_global_approach(self, mock_get_companies, mock_get_employees, mock_get_images):
        mock_get_companies.return_value = {
            'companies': [
                {'_type': 'company_type', 'company_id': '9183', 'name': 'Acme', 'ceo_id': '5791'},
                {'_type': 'company_type', 'company_id': '7261', 'name': 'Logo Makers', 'ceo_id': '51', 'logo_id': '65'},
            ],
        }

        mock_get_employees.return_value = {
            'employees': {
                '5791': {'_type': 'employee_type', 'employee_id': '5791', 'name': 'Julia', 'photo_id': '37'},
                '51': {'_type': 'employee_type', 'employee_id': '51', 'name': 'Nathan', 'photo_id': '79'},
            },
        }

        mock_get_images.side_effect = (
            {'images': {'65': {'image_id': '65', 'uri': '65.jpg'}}},
            {'images': {'37': {'image_id': '37', 'uri': '37.jpg'}, '79': {'image_id': '79', 'uri': '79.jpg'}}},
        )

        response = self.client.call_action(
            'company_service',
            'get_all_companies',
            body={},
            expansions={'company_type': ['ceo', 'logo'], 'employee_type': ['photo']},
        )

        mock_get_companies.assert_called_once_with({})
        mock_get_employees.assert_called_once_with({'employee_ids': AnyOrderEqualsList(['5791', '51'])})
        mock_get_images.assert_has_calls(
            [
                mock.call({'image_ids': ['65']}),
                mock.call({'image_ids': AnyOrderEqualsList(['37', '79'])}),
            ],
        )

        expected_response = {
            'companies': [
                {
                    '_type': 'company_type',
                    'company_id': '9183',
                    'name': 'Acme',
                    'ceo_id': '5791',
                    'ceo': {
                        '_type': 'employee_type',
                        'employee_id': '5791',
                        'name': 'Julia',
                        'photo_id': '37',
                        'photo': {'image_id': '37', 'uri': '37.jpg'},
                    },
                },
                {
                    '_type': 'company_type',
                    'company_id': '7261',
                    'name': 'Logo Makers',
                    'ceo_id': '51',
                    'ceo': {
                        '_type': 'employee_type',
                        'employee_id': '51',
                        'name': 'Nathan',
                        'photo_id': '79',
                        'photo': {'image_id': '79', 'uri': '79.jpg'},
                    },
                    'logo_id': '65',
                    'logo': {'image_id': '65', 'uri': '65.jpg'},
                },
            ],
        }

        self.assertEqual(expected_response, response.body)

    @stub_action('image_service', 'get_images_by_ids')
    @stub_action('employee_service', 'get_employees_reports_by_manager_ids')
    @stub_action('employee_service', 'get_employees_by_ids')
    @stub_action('company_service', 'get_all_companies')
    def test_expand_company_ceo_and_reports_nested_approach(
        self,
        mock_get_companies,
        mock_get_employees,
        mock_get_reports,
        mock_get_images,
    ):
        mock_get_companies.return_value = {
            'companies': [
                {'_type': 'company_type', 'company_id': '9183', 'name': 'Acme', 'ceo_id': '5791'},
                {'_type': 'company_type', 'company_id': '7261', 'name': 'Logo Makers', 'ceo_id': '51', 'logo_id': '65'},
            ],
        }

        mock_get_employees.return_value = {
            'employees': {
                '5791': {'_type': 'employee_type', 'employee_id': '5791', 'name': 'Julia', 'photo_id': '37'},
                '51': {'_type': 'employee_type', 'employee_id': '51', 'name': 'Nathan', 'photo_id': '79'},
            },
        }

        mock_get_reports.return_value = {
            'reports': {
                '5791': [
                    {'_type': 'employee_type', 'employee_id': '1039', 'name': 'Scott'},
                    {'_type': 'employee_type', 'employee_id': '1047', 'name': 'Whitney', 'photo_id': '41'},
                    {'_type': 'employee_type', 'employee_id': '1983', 'name': 'Matt', 'photo_id': None},
                ],
                '51': [
                    {'_type': 'employee_type', 'employee_id': '79', 'name': 'Jamie', 'photo_id': None},
                    {'_type': 'employee_type', 'employee_id': '68', 'name': 'Greg', 'photo_id': '16'},
                    {'_type': 'employee_type', 'employee_id': '413', 'name': 'Ralph', 'photo_id': '98'},
                    {'_type': 'employee_type', 'employee_id': '2706', 'name': 'Melanie'},
                ],
            },
        }

        mock_get_images.side_effect = (
            {'images': {'37': {'image_id': '37', 'uri': '37.jpg'}, '79': {'image_id': '79', 'uri': '79.jpg'}}},
            {
                'images': {
                    '41': {'image_id': '41', 'uri': '41.jpg'},
                    '16': {'image_id': '16', 'uri': '16.jpg'},
                    '98': {'image_id': '98', 'uri': '98.jpg'},
                },
            },
        )

        response = self.client.call_action(
            'company_service',
            'get_all_companies',
            body={},
            expansions={'company_type': ['ceo', 'ceo.photo', 'ceo.reports', 'ceo.reports.photo']},
        )

        mock_get_companies.assert_called_once_with({})
        mock_get_employees.assert_called_once_with({'employee_ids': AnyOrderEqualsList(['5791', '51'])})
        mock_get_reports.assert_called_once_with({'manager_ids': AnyOrderEqualsList(['5791', '51'])})
        mock_get_images.assert_has_calls(
            [
                mock.call({'image_ids': AnyOrderEqualsList(['37', '79'])}),
                mock.call({'image_ids': AnyOrderEqualsList(['41', '16', '98'])}),
            ],
        )

        expected_response = {
            'companies': [
                {
                    '_type': 'company_type',
                    'company_id': '9183',
                    'name': 'Acme',
                    'ceo_id': '5791',
                    'ceo': {
                        '_type': 'employee_type',
                        'employee_id': '5791',
                        'name': 'Julia',
                        'photo_id': '37',
                        'photo': {'image_id': '37', 'uri': '37.jpg'},
                        'reports': [
                            {'_type': 'employee_type', 'employee_id': '1039', 'name': 'Scott'},
                            {
                                '_type': 'employee_type',
                                'employee_id': '1047',
                                'name': 'Whitney',
                                'photo_id': '41',
                                'photo': {'image_id': '41', 'uri': '41.jpg'},
                            },
                            {'_type': 'employee_type', 'employee_id': '1983', 'name': 'Matt', 'photo_id': None},
                        ],
                    },
                },
                {
                    '_type': 'company_type',
                    'company_id': '7261',
                    'name': 'Logo Makers',
                    'ceo_id': '51',
                    'ceo': {
                        '_type': 'employee_type',
                        'employee_id': '51',
                        'name': 'Nathan',
                        'photo_id': '79',
                        'photo': {'image_id': '79', 'uri': '79.jpg'},
                        'reports': [
                            {'_type': 'employee_type', 'employee_id': '79', 'name': 'Jamie', 'photo_id': None},
                            {
                                '_type': 'employee_type',
                                'employee_id': '68',
                                'name': 'Greg',
                                'photo_id': '16',
                                'photo': {'image_id': '16', 'uri': '16.jpg'},
                            },
                            {
                                '_type': 'employee_type',
                                'employee_id': '413',
                                'name': 'Ralph',
                                'photo_id': '98',
                                'photo': {'image_id': '98', 'uri': '98.jpg'},
                            },
                            {'_type': 'employee_type', 'employee_id': '2706', 'name': 'Melanie'},
                        ],
                    },
                    'logo_id': '65',
                },
            ],
        }

        self.assertEqual(expected_response, response.body)

    @stub_action('image_service', 'get_images_by_ids')
    @stub_action('employee_service', 'get_employees_reports_by_manager_ids')
    @stub_action('employee_service', 'get_employees_by_ids')
    @stub_action('company_service', 'get_all_companies')
    def test_expand_company_ceo_and_reports_global_approach(
        self,
        mock_get_companies,
        mock_get_employees,
        mock_get_reports,
        mock_get_images,
    ):
        mock_get_companies.return_value = {
            'companies': [
                {'_type': 'company_type', 'company_id': '9183', 'name': 'Acme', 'ceo_id': '5791'},
                {'_type': 'company_type', 'company_id': '7261', 'name': 'Logo Makers', 'ceo_id': '51', 'logo_id': '65'},
            ],
        }

        mock_get_employees.return_value = {
            'employees': {
                '5791': {'_type': 'employee_type', 'employee_id': '5791', 'name': 'Julia', 'photo_id': '37'},
                '51': {'_type': 'employee_type', 'employee_id': '51', 'name': 'Nathan', 'photo_id': '79'},
            },
        }

        mock_get_reports.return_value = {
            'reports': {
                '5791': [
                    {'_type': 'employee_type', 'employee_id': '1039', 'name': 'Scott'},
                    {'_type': 'employee_type', 'employee_id': '1047', 'name': 'Whitney', 'photo_id': '41'},
                    {'_type': 'employee_type', 'employee_id': '1983', 'name': 'Matt', 'photo_id': None},
                ],
                '51': [
                    {'_type': 'employee_type', 'employee_id': '79', 'name': 'Jamie', 'photo_id': None},
                    {'_type': 'employee_type', 'employee_id': '68', 'name': 'Greg', 'photo_id': '16'},
                    {'_type': 'employee_type', 'employee_id': '413', 'name': 'Ralph', 'photo_id': '98'},
                    {'_type': 'employee_type', 'employee_id': '2706', 'name': 'Melanie'},
                ],
            },
        }

        mock_get_images.side_effect = (
            {'images': {'37': {'image_id': '37', 'uri': '37.jpg'}, '79': {'image_id': '79', 'uri': '79.jpg'}}},
            {
                'images': {
                    '41': {'image_id': '41', 'uri': '41.jpg'},
                    '16': {'image_id': '16', 'uri': '16.jpg'},
                    '98': {'image_id': '98', 'uri': '98.jpg'},
                },
            },
        )

        response = self.client.call_action(
            'company_service',
            'get_all_companies',
            body={},
            expansions={'company_type': ['ceo'], 'employee_type': ['photo', 'reports']},
        )

        mock_get_companies.assert_called_once_with({})
        mock_get_employees.assert_called_once_with({'employee_ids': AnyOrderEqualsList(['5791', '51'])})
        mock_get_reports.assert_has_calls(
            [
                mock.call({'manager_ids': AnyOrderEqualsList(['5791', '51'])}),
                mock.call({'manager_ids': AnyOrderEqualsList(['1039', '1047', '1983', '79', '68', '413', '2706'])}),
            ],
        )
        mock_get_images.assert_has_calls(
            [
                mock.call({'image_ids': AnyOrderEqualsList(['37', '79'])}),
                mock.call({'image_ids': AnyOrderEqualsList(['41', '16', '98'])}),
            ],
        )

        expected_response = {
            'companies': [
                {
                    '_type': 'company_type',
                    'company_id': '9183',
                    'name': 'Acme',
                    'ceo_id': '5791',
                    'ceo': {
                        '_type': 'employee_type',
                        'employee_id': '5791',
                        'name': 'Julia',
                        'photo_id': '37',
                        'photo': {'image_id': '37', 'uri': '37.jpg'},
                        'reports': [
                            {'_type': 'employee_type', 'employee_id': '1039', 'name': 'Scott'},
                            {
                                '_type': 'employee_type',
                                'employee_id': '1047',
                                'name': 'Whitney',
                                'photo_id': '41',
                                'photo': {'image_id': '41', 'uri': '41.jpg'},
                            },
                            {'_type': 'employee_type', 'employee_id': '1983', 'name': 'Matt', 'photo_id': None},
                        ],
                    },
                },
                {
                    '_type': 'company_type',
                    'company_id': '7261',
                    'name': 'Logo Makers',
                    'ceo_id': '51',
                    'ceo': {
                        '_type': 'employee_type',
                        'employee_id': '51',
                        'name': 'Nathan',
                        'photo_id': '79',
                        'photo': {'image_id': '79', 'uri': '79.jpg'},
                        'reports': [
                            {'_type': 'employee_type', 'employee_id': '79', 'name': 'Jamie', 'photo_id': None},
                            {
                                '_type': 'employee_type',
                                'employee_id': '68',
                                'name': 'Greg',
                                'photo_id': '16',
                                'photo': {'image_id': '16', 'uri': '16.jpg'},
                            },
                            {
                                '_type': 'employee_type',
                                'employee_id': '413',
                                'name': 'Ralph',
                                'photo_id': '98',
                                'photo': {'image_id': '98', 'uri': '98.jpg'},
                            },
                            {'_type': 'employee_type', 'employee_id': '2706', 'name': 'Melanie'},
                        ],
                    },
                    'logo_id': '65',
                },
            ],
        }

        self.assertEqual(expected_response, response.body)

    @stub_action('image_service', 'get_images_by_ids')
    @stub_action('employee_service', 'get_employees_by_ids')
    @stub_action('employee_service', 'get_company_employees_by_company_ids')
    @stub_action('company_service', 'get_all_companies')
    def test_expand_company_employees_and_managers(
        self,
        mock_get_companies,
        mock_get_employees,
        mock_get_managers,
        mock_get_images,
    ):
        mock_get_companies.return_value = {
            'companies': [
                {'_type': 'company_type', 'company_id': '9183', 'name': 'Acme', 'ceo_id': '5791'},
                {'_type': 'company_type', 'company_id': '7261', 'name': 'Logo Makers', 'ceo_id': '51', 'logo_id': '65'},
            ],
        }

        mock_get_employees.return_value = {
            'employees': {
                '9183': [
                    {'_type': 'employee_type', 'employee_id': '5791', 'name': 'Julia', 'photo_id': '37'},
                    {'_type': 'employee_type', 'employee_id': '1039', 'name': 'Scott', 'manager_id': '5791'},
                    {
                        '_type': 'employee_type',
                        'employee_id': '1047',
                        'name': 'Whitney',
                        'photo_id': '41',
                        'manager_id': '5791',
                    },
                    {
                        '_type': 'employee_type',
                        'employee_id': '1983',
                        'name': 'Matt',
                        'photo_id': None,
                        'manager_id': '5791',
                    },
                ],
                '7261': [
                    {'_type': 'employee_type', 'employee_id': '51', 'name': 'Nathan', 'photo_id': '79'},
                    {
                        '_type': 'employee_type',
                        'employee_id': '79',
                        'name': 'Jamie',
                        'photo_id': None,
                        'manager_id': '51',
                    },
                    {
                        '_type': 'employee_type',
                        'employee_id': '68',
                        'name': 'Greg',
                        'photo_id': '16',
                        'manager_id': '51',
                    },
                    {
                        '_type': 'employee_type',
                        'employee_id': '413',
                        'name': 'Ralph',
                        'photo_id': '98',
                        'manager_id': '51',
                    },
                    {'_type': 'employee_type', 'employee_id': '2706', 'name': 'Melanie', 'manager_id': '51'},
                ],
            },
        }

        mock_get_managers.return_value = {
            'employees': {
                '5791': {'_type': 'employee_type', 'employee_id': '5791', 'name': 'Julia', 'photo_id': '37'},
                '51': {'_type': 'employee_type', 'employee_id': '51', 'name': 'Nathan', 'photo_id': '79'},
            },
        }

        mock_get_images.side_effect = (
            {
                'images': {
                    '37': {'image_id': '37', 'uri': '37.jpg'},
                    '79': {'image_id': '79', 'uri': '79.jpg'},
                    '41': {'image_id': '41', 'uri': '41.jpg'},
                    '16': {'image_id': '16', 'uri': '16.jpg'},
                    '98': {'image_id': '98', 'uri': '98.jpg'},
                },
            },
            {'images': {'37': {'image_id': '37', 'uri': '37.jpg'}, '79': {'image_id': '79', 'uri': '79.jpg'}}},
        )

        response = self.client.call_action(
            'company_service',
            'get_all_companies',
            body={},
            expansions={
                'company_type': ['employees', 'employees.photo', 'employees.manager', 'employees.manager.photo'],
            },
        )

        mock_get_companies.assert_called_once_with({})
        mock_get_employees.assert_called_once_with({'company_ids': AnyOrderEqualsList(['9183', '7261'])})
        mock_get_managers.assert_called_once_with({'employee_ids': AnyOrderEqualsList(['5791', '51'])})
        mock_get_images.assert_has_calls(
            [
                mock.call({'image_ids': AnyOrderEqualsList(['37', '41', '79', '16', '98'])}),
            ],
        )

        expected_response = {
            'companies': [
                {
                    '_type': 'company_type',
                    'company_id': '9183',
                    'name': 'Acme',
                    'ceo_id': '5791',
                    'employees': [
                        {
                            '_type': 'employee_type',
                            'employee_id': '5791',
                            'name': 'Julia',
                            'photo_id': '37',
                            'photo': {'image_id': '37', 'uri': '37.jpg'},
                        },
                        {
                            '_type': 'employee_type',
                            'employee_id': '1039',
                            'name': 'Scott',
                            'manager_id': '5791',
                            'manager': {
                                '_type': 'employee_type',
                                'employee_id': '5791',
                                'name': 'Julia',
                                'photo_id': '37',
                            },
                        },
                        {
                            '_type': 'employee_type',
                            'employee_id': '1047',
                            'name': 'Whitney',
                            'photo_id': '41',
                            'photo': {'image_id': '41', 'uri': '41.jpg'},
                            'manager_id': '5791',
                            'manager': {
                                '_type': 'employee_type',
                                'employee_id': '5791',
                                'name': 'Julia',
                                'photo_id': '37',
                            },
                        },
                        {
                            '_type': 'employee_type',
                            'employee_id': '1983',
                            'name': 'Matt',
                            'photo_id': None,
                            'manager_id': '5791',
                            'manager': {
                                '_type': 'employee_type',
                                'employee_id': '5791',
                                'name': 'Julia',
                                'photo_id': '37',
                            },
                        },
                    ],
                },
                {
                    '_type': 'company_type',
                    'company_id': '7261',
                    'name': 'Logo Makers',
                    'ceo_id': '51',
                    'logo_id': '65',
                    'employees': [
                        {
                            '_type': 'employee_type',
                            'employee_id': '51',
                            'name': 'Nathan',
                            'photo_id': '79',
                            'photo': {'image_id': '79', 'uri': '79.jpg'},
                        },
                        {
                            '_type': 'employee_type',
                            'employee_id': '79',
                            'name': 'Jamie',
                            'photo_id': None,
                            'manager_id': '51',
                            'manager': {
                                '_type': 'employee_type',
                                'employee_id': '51',
                                'name': 'Nathan',
                                'photo_id': '79',
                            },
                        },
                        {
                            '_type': 'employee_type',
                            'employee_id': '68',
                            'name': 'Greg',
                            'photo_id': '16',
                            'photo': {'image_id': '16', 'uri': '16.jpg'},
                            'manager_id': '51',
                            'manager': {
                                '_type': 'employee_type',
                                'employee_id': '51',
                                'name': 'Nathan',
                                'photo_id': '79',
                            },
                        },
                        {
                            '_type': 'employee_type',
                            'employee_id': '413',
                            'name': 'Ralph',
                            'photo_id': '98',
                            'photo': {'image_id': '98', 'uri': '98.jpg'},
                            'manager_id': '51',
                            'manager': {
                                '_type': 'employee_type',
                                'employee_id': '51',
                                'name': 'Nathan',
                                'photo_id': '79',
                            },
                        },
                        {
                            '_type': 'employee_type',
                            'employee_id': '2706',
                            'name': 'Melanie',
                            'manager_id': '51',
                            'manager': {
                                '_type': 'employee_type',
                                'employee_id': '51',
                                'name': 'Nathan',
                                'photo_id': '79',
                            },
                        },
                    ],
                },
            ],
        }

        self.assertEqual(expected_response, response.body)
