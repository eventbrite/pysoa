from __future__ import (
    absolute_import,
    unicode_literals,
)

import logging
import logging.handlers
import socket
import threading

import six


class PySOALogContextFilter(logging.Filter):
    def __init__(self):
        super(PySOALogContextFilter, self).__init__('')

    def filter(self, record):
        context = self.get_logging_request_context()
        if context:
            record.correlation_id = context.get('correlation_id') or '--'
            record.request_id = context.get('request_id') or '--'
        else:
            record.correlation_id = '--'
            record.request_id = '--'
        record.service_name = self._service_name or 'unknown'
        return True

    _logging_context = threading.local()

    _service_name = None

    @classmethod
    def set_logging_request_context(cls, **context):
        if not getattr(cls._logging_context, 'context_stack', None):
            cls._logging_context.context_stack = []
        cls._logging_context.context_stack.append(context)

    @classmethod
    def clear_logging_request_context(cls):
        if getattr(cls._logging_context, 'context_stack', None):
            cls._logging_context.context_stack.pop()

    @classmethod
    def get_logging_request_context(cls):
        if getattr(cls._logging_context, 'context_stack', None):
            return cls._logging_context.context_stack[-1]
        return None

    @classmethod
    def set_service_name(cls, service_name):
        cls._service_name = service_name


class RecursivelyCensoredDictWrapper(object):
    # Some performance info about this set
    #
    # In [1]: %timeit 'password' in SENSITIVE_FIELDS
    # The slowest run took 16.69 times longer than the fastest. This could mean that an intermediate result is being
    # cached.
    # 10000000 loops, best of 3: 129 ns per loop
    #
    # In [2]: %timeit 'nope' in SENSITIVE_FIELDS
    # 10000000 loops, best of 3: 131 ns per loop
    #
    # In [3]: %timeit random_string()
    # 100000 loops, best of 3: 10.4 us per loop
    #
    # In [4]: %timeit random_string() in SENSITIVE_FIELDS
    # 100000 loops, best of 3: 10.7 us per loop
    #
    # Suffice it to say, a lookup against this set should always take less than 250 ns.
    SENSITIVE_FIELDS = frozenset({
        # Authentication and related
        'password', 'pass', 'passwd', 'passphrase', 'pass_phrase', 'pass-phrase', 'passPhrase',
        'passwords', 'passwds', 'passphrases', 'pass_phrases', 'pass-phrases', 'passPhrases',
        'private', 'private_key', 'private-key', 'privateKey',
        'privates', 'private_keys', 'private-keys', 'privateKeys',
        'secret', 'secret_key', 'secret-key', 'secretKey',
        'secrets', 'secret_keys', 'secret-keys', 'secretKeys',
        'security_code', 'security-code', 'securityCode',
        'security_codes', 'security-codes', 'securityCodes',
        'auth', 'token', 'auth_token', 'auth-token', 'authToken',
        'authorization', 'authorization_token', 'authorization-token', 'authorizationToken',
        'authentication', 'authentication_token', 'authentication-token', 'authenticationToken',

        # Credit cards, banking, and related
        'credit_card', 'credit-card', 'creditCard', 'credit_card_number', 'credit-card-number', 'creditCardNumber',
        'card_number', 'card-number', 'cardNumber', 'cc_number', 'cc-number', 'ccNumber', 'ccn',
        'credit_cards', 'credit-cards', 'creditCards', 'credit_card_numbers', 'credit-card-numbers',
        'creditCardNumbers',
        'card_numbers', 'card-numbers', 'cardNumbers', 'cc_numbers', 'cc-numbers', 'ccNumbers', 'ccns',
        'cid', 'csc', 'csn', 'cvc', 'cvc2', 'cvd', 'cve', 'cvn2', 'cvv', 'cvv2', 'icvv',
        'cids', 'cscs', 'csns', 'cvcs', 'cvc2s', 'cvds', 'cves', 'cvn2s', 'cvvs', 'cvv2s', 'icvvs',
        'card_id', 'card-id', 'cardId', 'card_identification', 'card-identification', 'cardIdentification',
        'card_ids', 'card-ids', 'cardIds', 'card_identifications', 'card-identifications', 'cardIdentifications',
        'card_identification_code', 'card-identification-code', 'cardIdentificationCode',
        'card_identification_codes', 'card-identification-codes', 'cardIdentificationCodes',
        'card_identification_number', 'card-identification-number', 'cardIdentificationNumber',
        'card_identification_numbers', 'card-identification-numbers', 'cardIdentificationNumbers',
        'card_identification_value', 'card-identification-value', 'cardIdentificationValue',
        'card_identification_values', 'card-identification-values', 'cardIdentificationValues',
        'card_security', 'card-security', 'cardSecurity',
        'card_securities', 'card-securities', 'cardSecurities',
        'card_security_code', 'card-security-code', 'cardSecurityCode',
        'card_security_codes', 'card-security-codes', 'cardSecurityCodes',
        'card_security_number', 'card-security-number', 'cardSecurityNumber',
        'card_security_numbers', 'card-security-numbers', 'cardSecurityNumbers',
        'card_security_value', 'card-security-value', 'cardSecurityValue',
        'card_security_values', 'card-security-values', 'cardSecurityValues',
        'card_validation', 'card-validation', 'cardValidation',
        'card_validations', 'card-validations', 'cardValidations',
        'card_validation_code', 'card-validation-code', 'cardValidationCode',
        'card_validation_codes', 'card-validation-codes', 'cardValidationCodes',
        'card_validation_number', 'card-validation-number', 'cardValidationNumber',
        'card_validation_numbers', 'card-validation-numbers', 'cardValidationNumbers',
        'card_validation_value', 'card-validation-value', 'cardValidationValue',
        'card_validation_values', 'card-validation-values', 'cardValidationValues',
        'card_verification', 'card-verification', 'cardVerification',
        'card_verifications', 'card-verifications', 'cardVerifications',
        'card_verification_code', 'card-verification-code', 'cardVerificationCode',
        'card_verification_codes', 'card-verification-codes', 'cardVerificationCodes',
        'card_verification_number', 'card-verification-number', 'cardVerificationNumber',
        'card_verification_numbers', 'card-verification-numbers', 'cardVerificationNumbers',
        'card_verification_value', 'card-verification-value', 'cardVerificationValue',
        'card_verification_values', 'card-verification-values', 'cardVerificationValues',
        'account_number', 'account-number', 'accountNumber',
        'account_numbers', 'account-numbers', 'accountNumbers',
        'bank_account', 'bank-account', 'bankAccount',
        'bank_accounts', 'bank-accounts', 'bankAccounts',
        'bank_account_number', 'bank-account-number', 'bankAccountNumber',
        'bank_account_numbers', 'bank-account-numbers', 'bankAccountNumbers',
        'pin', 'pin_code', 'pin-code', 'pinCode', 'pin_number', 'pin-number', 'pinNumber',
        'pins', 'pin_codes', 'pin-codes', 'pinCodes', 'pin_numbers', 'pin-numbers', 'pinNumbers',
        'personal_id_number', 'personal-id-number', 'personalIdNumber',
        'personal_id_numbers', 'personal-id-numbers', 'personalIdNumbers',
        'personal_identification_number', 'personal-identification-number', 'personalIdentificationNumber',
        'personal_identification_numbers', 'personal-identification-numbers', 'personalIdentificationNumbers',
    })

    CENSOR_TYPES = six.string_types + six.integer_types

    CENSORED_STRING = '**********'

    def __init__(self, wrapped_dict):
        """
        Wraps a dict to censor its contents. The first time `repr` is called, it copies the dict, recursively
        censors sensitive fields, caches the result, and returns the censored dict repr-ed. All future calls use
        the cache.

        :param wrapped_dict: The `dict` that should be censored
        :type wrapped_dict: dict
        """
        if not isinstance(wrapped_dict, dict):
            raise ValueError('wrapped_dict must be a dict')

        self._wrapped_dict = wrapped_dict
        self._dict_cache = None
        self._repr_cache = None

    def _get_repr_cache(self):
        if not self._dict_cache:
            self._dict_cache = self._copy_and_censor_dict(self._wrapped_dict)

        return repr(self._dict_cache)

    def __repr__(self):
        if not self._repr_cache:
            self._repr_cache = self._get_repr_cache()
        return self._repr_cache

    def __str__(self):
        return self.__repr__()

    def __bytes__(self):
        # If this method is called, we must be in Python 3, which means __str__ must be returning a string
        return self.__str__().encode('utf-8')

    def __unicode__(self):
        # If this method is called, we must be in Python 2, which means __str__ must be returning bytes
        # noinspection PyUnresolvedReferences
        return self.__str__().decode('utf-8')

    @classmethod
    def _copy_and_censor_unknown_value(cls, v, should_censor_strings):
        if isinstance(v, dict):
            return cls._copy_and_censor_dict(v)

        if isinstance(v, (list, tuple, set, frozenset)):
            return cls._copy_and_censor_iterable(v, should_censor_strings)

        if should_censor_strings and v and isinstance(v, cls.CENSOR_TYPES) and not isinstance(v, bool):
            return cls.CENSORED_STRING

        return v

    @classmethod
    def _copy_and_censor_dict(cls, d):
        # This should only be _marginally_ slower than copy.deepcopy
        return {k: cls._copy_and_censor_unknown_value(v, k in cls.SENSITIVE_FIELDS) for k, v in six.iteritems(d)}

    @classmethod
    def _copy_and_censor_iterable(cls, i, should_censor_strings):
        return type(i)(cls._copy_and_censor_unknown_value(v, should_censor_strings) for v in i)


IP_MTU_DISCOVER = 10  # Position of the IP Path MTU Discovery flag in request packets
IP_MTU_DISCOVER_DO = 2  # "Don't fragment" value of the IP Path MTU Discovery flag in request packets
WORST_CASE_MTU_IP = 576
MTU_ATTEMPTS = 65535, 2000, 1500, 1280
DATAGRAM_HEADER_LENGTH_IN_BYTES = 28


def _discover_minimum_mtu_to_target(address, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((address, port))
    s.setsockopt(socket.IPPROTO_IP, IP_MTU_DISCOVER, IP_MTU_DISCOVER_DO)
    for attempt in MTU_ATTEMPTS:
        try:
            s.send(b'#' * (attempt - DATAGRAM_HEADER_LENGTH_IN_BYTES))
            return attempt
        except socket.error as e:
            if 'too long' not in e.strerror:
                # We can't rely on the error code, because it varies from platform to platform, but the message always
                # contains "too long" if we're getting an "MTU exceeded" ICMP response. IF this isn't an "MTU exceeded"
                # response, then something went wrong, and we can't determine the MTU, so fall back to worst case.
                break
            # Now we try again with a lower MTU, which might still be too high
    return WORST_CASE_MTU_IP


class SyslogHandler(logging.handlers.SysLogHandler):
    """
    A more advanced Syslog logging handler that attempts to understand the MTU of the underlying connection and then
    tailor Syslog packets to match that MTU, either by truncating or splitting logging packets. This contrasts to the
    superclass, which will simply drop packets that exceed the MTU (optionally logging an error about the failure).

    Notes:
        The maximum UDP packet header in bytes is 28 bytes (20 bytes IP header + 8 bytes UDP header). Note that the
        optional 40-byte IP header options could make this 68 bytes, but this is rarely used, and this handler does not
        use it.

        The Syslog priority and facility are encoded into a single 32-bit (4-byte) value.
    """
    OVERFLOW_BEHAVIOR_FRAGMENT = 0
    OVERFLOW_BEHAVIOR_TRUNCATE = 1

    _MINIMUM_MTU_CACHE = {}

    def __init__(
        self,
        address=('localhost', logging.handlers.SYSLOG_UDP_PORT),
        facility=logging.handlers.SysLogHandler.LOG_USER,
        socket_type=None,
        overflow=OVERFLOW_BEHAVIOR_FRAGMENT,
    ):
        super(SyslogHandler, self).__init__(address, facility, socket_type)

        if not self.unixsocket and self.socktype == socket.SOCK_DGRAM:
            if address[0] not in self._MINIMUM_MTU_CACHE:
                # The MTU is unlikely to change while the process is running, and checking it is expensive
                self._MINIMUM_MTU_CACHE[address[0]] = _discover_minimum_mtu_to_target(address[0], 9999)

            self.maximum_length = self._MINIMUM_MTU_CACHE[address[0]] - DATAGRAM_HEADER_LENGTH_IN_BYTES
            self.overflow = overflow
        else:
            self.maximum_length = 1048576  # Let's not send more than a megabyte to Syslog, even over TCP/Unix ... crazy
            self.overflow = self.OVERFLOW_BEHAVIOR_TRUNCATE

    def emit(self, record):
        """
        Emits a record. The record is sent carefully, according to the following rules, to ensure that data is not
        lost by exceeding the MTU of the connection.

        - If the byte-encoded record length plus prefix length plus suffix length plus priority length is less than the
          maximum allowed length, then a single packet is sent, containing the priority, prefix, full record, and
          suffix, in that order.

        - If it's greater than or equal to the maximum allowed length and the overflow behavior is set to "truncate,"
          the record is cleanly truncated (being careful not to split in the middle of a multi-byte character), and
          then a single packet is sent, containing the priority, prefix, truncated record, and suffix, in that order.

        - If it's greater than or equal to the maximum allowed length and the overflow behavior is set to "fragment,"
          the record preamble (things like file name, logger name, correlation ID, etc.) is extracted from the start
          of the record to calculate a new chunk length. The remainder of the record (which should just be the true
          message and any exception info) is then chunked (being careful not to split in the middle of a multi-byte
          character) into lengths less than or equal to the chunk length, and then the record is sent as multiple
          packets, each packet containing the priority, prefix, record preamble, message chunk, and suffix, in that
          order.
        """
        # noinspection PyBroadException
        try:
            formatted_message = self.format(record)
            encoded_message = formatted_message.encode('utf-8')

            prefix = suffix = b''
            if getattr(self, 'ident', False):
                prefix = self.ident.encode('utf-8') if isinstance(self.ident, six.text_type) else self.ident
            if getattr(self, 'append_nul', True):
                suffix = '\000'.encode('utf-8')

            priority = '<{:d}>'.format(
                self.encodePriority(self.facility, self.mapPriority(record.levelname))
            ).encode('utf-8')

            message_length = len(encoded_message)
            message_length_limit = self.maximum_length - len(prefix) - len(suffix) - len(priority)

            if message_length < message_length_limit:
                parts = [priority + prefix + encoded_message + suffix]
            elif self.overflow == self.OVERFLOW_BEHAVIOR_TRUNCATE:
                truncated_message, _ = self._cleanly_slice_encoded_string(encoded_message, message_length_limit)
                parts = [priority + prefix + truncated_message + suffix]
            else:
                # This can't work perfectly, but it's pretty unusual for a message to go before machine-parseable parts
                # in the formatted record. So we split the record on the message part. Everything before the split
                # becomes the preamble and gets repeated every packet. Everything after the split gets chunked. There's
                # no reason to match on more than the first 40 characters of the message--the chances of that matching
                # the wrong part of the record are astronomical.
                try:
                    index = formatted_message.index(record.getMessage()[:40])
                    start_of_message, to_chunk = formatted_message[:index], formatted_message[index:]
                except (TypeError, ValueError):
                    # We can't locate the message in the formatted record? That's unfortunate. Let's make something up.
                    start_of_message, to_chunk = '{} '.format(formatted_message[:30]), formatted_message[30:]

                start_of_message = start_of_message.encode('utf-8')
                to_chunk = to_chunk.encode('utf-8')

                # 12 is the length of "... (cont'd)" in bytes
                chunk_length_limit = message_length_limit - len(start_of_message) - 12

                i = 1
                parts = []
                remaining_message = to_chunk
                while remaining_message:
                    message_id = b''
                    subtractor = 0
                    if i > 1:
                        # If this is not the first message, we determine message # so that we can subtract that length
                        message_id = '{}'.format(i).encode('utf-8')
                        # 14 is the length of "(cont'd #) ..." in bytes
                        subtractor = 14 + len(message_id)
                    chunk, remaining_message = self._cleanly_slice_encoded_string(
                        remaining_message,
                        chunk_length_limit - subtractor,
                    )
                    if i > 1:
                        # If this is not the first message, we prepend the chunk to indicate continuation
                        chunk = b"(cont'd #" + message_id + b') ...' + chunk
                    i += 1
                    if remaining_message:
                        # If this is not the last message, we append the chunk to indicate continuation
                        chunk = chunk + b"... (cont'd)"
                    parts.append(priority + prefix + start_of_message + chunk + suffix)

            self._send(parts)
        except Exception:
            self.handleError(record)

    def _send(self, parts):
        for message in parts:
            if self.unixsocket:
                try:
                    self.socket.send(message)
                except OSError:
                    self.socket.close()
                    self._connect_unixsocket(self.address)
                    self.socket.send(message)
            elif self.socktype == socket.SOCK_DGRAM:
                self.socket.sendto(message, self.address)
            else:
                self.socket.sendall(message)

    @staticmethod
    def _cleanly_slice_encoded_string(encoded_string, length_limit):
        """
        Takes a byte string (a UTF-8 encoded string) and splits it into two pieces such that the first slice is no
        longer than argument `length_limit`, then returns a tuple containing the first slice and remainder of the
        byte string, respectively. The first slice may actually be shorter than `length_limit`, because this ensures
        that the string does not get split in the middle of a multi-byte character.

        This works because the first byte in a multi-byte unicode character encodes how many bytes compose that
        character, so we can determine empirically if we are splitting in the middle of the character and correct for
        that.

        You can read more about how this works here: https://en.wikipedia.org/wiki/UTF-8#Description

        :param encoded_string: The encoded string to split in two
        :param length_limit: The maximum length allowed for the first slice of the string
        :return: A tuple of (slice, remaining)
        """
        sliced, remaining = encoded_string[:length_limit], encoded_string[length_limit:]
        try:
            sliced.decode('utf-8')
        except UnicodeDecodeError as e:
            sliced, remaining = sliced[:e.start], sliced[e.start:] + remaining

        return sliced, remaining
