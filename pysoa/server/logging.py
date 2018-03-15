from __future__ import absolute_import, unicode_literals

import logging
import threading

import six


class PySOALogContextFilter(logging.Filter):
    def __init__(self):
        super(PySOALogContextFilter, self).__init__('')

    def filter(self, record):
        context = self.get_logging_request_context()
        if context:
            record.correlation_id = context.get('correlation_id') or ''
            record.request_id = context.get('request_id') or ''
        else:
            record.correlation_id = ''
            record.request_id = ''
        return True

    _logging_context = threading.local()

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
