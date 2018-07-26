from __future__ import (
    absolute_import,
    unicode_literals,
)

import codecs
import contextlib
import tempfile
import unittest

from pysoa.test.plan.errors import (
    FixtureLoadError,
    FixtureSyntaxError,
)
from pysoa.test.plan.parser import ServiceTestPlanFixtureParser


@contextlib.contextmanager
def _temp_fixture_file_name_context(contents):
    temp_file = tempfile.NamedTemporaryFile(mode='wb')
    codec = codecs.lookup('utf-8')
    with codecs.StreamReaderWriter(temp_file, codec.streamreader, codec.streamwriter, 'strict') as writer:
        writer.write(contents)
        writer.flush()

        yield temp_file.name


class TestParserAndGrammarErrors(unittest.TestCase):
    def test_no_file(self):
        parser = ServiceTestPlanFixtureParser('/path/to/fake/fixture', 'test_no_file')
        with self.assertRaises(FixtureLoadError):
            parser.parse_test_fixture()

    def test_empty_file(self):
        with _temp_fixture_file_name_context('\n') as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_empty_file')
            with self.assertRaises(FixtureLoadError):
                parser.parse_test_fixture()

    def test_general_syntax_error(self):
        # missing colon after expect
        fixture = """test name: some_test
test description: Some description
get_user: input int: user_id: 123
get_user: expect no errors
"""

        with _temp_fixture_file_name_context(fixture) as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_general_syntax_error')
            with self.assertRaises(FixtureSyntaxError) as error_context:
                parser.parse_test_fixture()

        self.assertIn('Failed to parse line', error_context.exception.msg)
        self.assertIn('get_user: expect no errors', error_context.exception.msg)
        self.assertIn(file_name, error_context.exception.msg)
        self.assertIn('Expected end of text', error_context.exception.msg)
        self.assertEqual(file_name, error_context.exception.filename)
        self.assertEqual(4, error_context.exception.lineno)
        self.assertEqual('get_user: expect no errors', error_context.exception.text)
        self.assertEqual(1, error_context.exception.offset)

    def test_data_type_conversion_error(self):
        # invalid integer for user ID
        fixture = """test name: some_test
test description: Some description
get_user: input int: user_id: abc123
get_user: expect: no errors
"""

        with _temp_fixture_file_name_context(fixture) as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_data_type_conversion_error')
            with self.assertRaises(FixtureSyntaxError) as error_context:
                parser.parse_test_fixture()

        self.assertIn('Data type conversion error', error_context.exception.msg)
        self.assertIn(file_name, error_context.exception.msg)
        self.assertIn('invalid literal', error_context.exception.msg)
        self.assertIn('with base 10', error_context.exception.msg)
        self.assertEqual(file_name, error_context.exception.filename)
        self.assertEqual(3, error_context.exception.lineno)
        self.assertEqual('get_user: input int: user_id: abc123', error_context.exception.text)
        self.assertEqual(36, error_context.exception.offset)

    def test_test_case_without_name(self):
        # missing name
        fixture = """test description: Some description
get_user: input int: user_id: 123
get_user: expect: no errors
"""

        with _temp_fixture_file_name_context(fixture) as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_test_case_without_name')
            with self.assertRaises(FixtureSyntaxError) as error_context:
                parser.parse_test_fixture()

        self.assertIn('Test case without name', error_context.exception.msg)
        self.assertIn(file_name, error_context.exception.msg)
        self.assertEqual(file_name, error_context.exception.filename)
        self.assertEqual(3, error_context.exception.lineno)
        self.assertEqual('get_user: expect: no errors', error_context.exception.text)
        self.assertEqual(27, error_context.exception.offset)

    def test_test_case_without_description(self):
        # missing description
        fixture = """test name: some_test
get_user: input int: user_id: 123
get_user: expect: no errors
"""

        with _temp_fixture_file_name_context(fixture) as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_test_case_without_description')
            with self.assertRaises(FixtureSyntaxError) as error_context:
                parser.parse_test_fixture()

        self.assertIn('Test case without description', error_context.exception.msg)
        self.assertIn(file_name, error_context.exception.msg)
        self.assertEqual(file_name, error_context.exception.filename)
        self.assertEqual(3, error_context.exception.lineno)
        self.assertEqual('get_user: expect: no errors', error_context.exception.text)
        self.assertEqual(27, error_context.exception.offset)

    def test_empty_test_case(self):
        # missing action cases
        fixture = """test name: some_test
test description: Some description
"""

        with _temp_fixture_file_name_context(fixture) as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_empty_test_case')
            with self.assertRaises(FixtureSyntaxError) as error_context:
                parser.parse_test_fixture()

        self.assertIn('Empty test case', error_context.exception.msg)
        self.assertIn(file_name, error_context.exception.msg)
        self.assertEqual(file_name, error_context.exception.filename)
        self.assertEqual(2, error_context.exception.lineno)
        self.assertEqual('test description: Some description', error_context.exception.text)
        self.assertEqual(34, error_context.exception.offset)

    def test_duplicate_test_name_directive_same_name(self):
        # duplicate test name directive
        fixture = """test name: some_test
test name: some_test
test description: Some description
get_user: input int: user_id: 123
get_user: expect: no errors
"""

        with _temp_fixture_file_name_context(fixture) as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_duplicate_test_name')
            with self.assertRaises(FixtureSyntaxError) as error_context:
                parser.parse_test_fixture()

        self.assertIn('Duplicate test name directive for test case', error_context.exception.msg)
        self.assertEqual(file_name, error_context.exception.filename)
        self.assertEqual(2, error_context.exception.lineno)
        self.assertEqual('test name: some_test', error_context.exception.text)
        self.assertEqual(20, error_context.exception.offset)

    def test_duplicate_test_name_directive_different_name(self):
        # duplicate test name directive
        fixture = """test name: some_test
test name: another_test
test description: Some description
get_user: input int: user_id: 123
get_user: expect: no errors
"""

        with _temp_fixture_file_name_context(fixture) as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_duplicate_test_name')
            with self.assertRaises(FixtureSyntaxError) as error_context:
                parser.parse_test_fixture()

        self.assertIn('Duplicate test name directive for test case', error_context.exception.msg)
        self.assertEqual(file_name, error_context.exception.filename)
        self.assertEqual(2, error_context.exception.lineno)
        self.assertEqual('test name: another_test', error_context.exception.text)
        self.assertEqual(23, error_context.exception.offset)

    def test_duplicate_test_description_directive_same_description(self):
        # duplicate test description directive
        fixture = """test name: some_test
test description: Some description
test description: Some description
get_user: input int: user_id: 123
get_user: expect: no errors
"""

        with _temp_fixture_file_name_context(fixture) as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_duplicate_test_description')
            with self.assertRaises(FixtureSyntaxError) as error_context:
                parser.parse_test_fixture()

        self.assertIn('Duplicate test description directive for test case', error_context.exception.msg)
        self.assertEqual(file_name, error_context.exception.filename)
        self.assertEqual(3, error_context.exception.lineno)
        self.assertEqual('test description: Some description', error_context.exception.text)
        self.assertEqual(34, error_context.exception.offset)

    def test_duplicate_test_description_directive_different_description(self):
        # duplicate test description directive
        fixture = """test name: some_test
test description: Some description
test description: A different description
get_user: input int: user_id: 123
get_user: expect: no errors
"""

        with _temp_fixture_file_name_context(fixture) as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_duplicate_test_description')
            with self.assertRaises(FixtureSyntaxError) as error_context:
                parser.parse_test_fixture()

        self.assertIn('Duplicate test description directive for test case', error_context.exception.msg)
        self.assertEqual(file_name, error_context.exception.filename)
        self.assertEqual(3, error_context.exception.lineno)
        self.assertEqual('test description: A different description', error_context.exception.text)
        self.assertEqual(41, error_context.exception.offset)

    def test_invalid_freeze_time_syntax(self):
        # invalid freeze time syntax
        fixture = """test name: some_test
test description: Some description
get_user: freeze time: not a valid date time string
get_user: input int: user_id: 123
get_user: expect: no errors
"""

        with _temp_fixture_file_name_context(fixture) as file_name:
            parser = ServiceTestPlanFixtureParser(file_name, 'test_invalid_freeze_time_syntax')
            with self.assertRaises(FixtureSyntaxError) as error_context:
                parser.parse_test_fixture()

        self.assertIn('Could not parse datetime value for time freeze', error_context.exception.msg)
        self.assertEqual(file_name, error_context.exception.filename)
        self.assertEqual(3, error_context.exception.lineno)
        self.assertEqual('get_user: freeze time: not a valid date time string', error_context.exception.text)
        self.assertEqual(51, error_context.exception.offset)
