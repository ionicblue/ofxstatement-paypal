# -*- coding: utf-8 -*-

import locale
import itertools
import csv

from datetime import datetime

from contextlib import contextmanager
from ofxstatement.parser import StatementParser
from ofxstatement.plugin import Plugin
from ofxstatement.statement import Statement, StatementLine, generate_transaction_id


def take(iterable, n):
    """Return first n items of the iterable as a list."""
    return list(itertools.islice(iterable, n))


def drop(iterable, n):
    """Drop first n items of the iterable and return result as a list."""
    return list(itertools.islice(iterable, n, None))


def head(iterable):
    """Return first element of the iterable."""
    return take(iterable, 1)[0]


@contextmanager
def scoped_setlocale(category, loc=None):
    """Scoped version of locale.setlocale()"""
    orig = locale.getlocale(category)
    try:
        yield locale.setlocale(category, loc)
    finally:
        locale.setlocale(category, orig)


def atof(string, loc=None):
    """Locale aware atof function for our parser."""
    with scoped_setlocale(locale.LC_NUMERIC, loc):
        return locale.atof(string)


class PayPalStatementParser(StatementParser):
    bank_id = 'PayPal'
    date_format = '%d/%m/%Y'
    valid_header = [
        u"Date",
        u"Time",
        u"TimeZone",
        u"Name",
        u"Type",
        u"Status",
        u"Currency",
        u"Amount",
        u"Receipt ID",
        u"Balance",
    ]

    def __init__(self, fin, account_id, currency, encoding=None, locale=None, analyze=False):
        self.account_id = account_id
        self.currency = currency
        self.locale = locale
        self.encoding = encoding
        self.analyze = analyze

        with open(fin, 'r', encoding=self.encoding) as f:
            self.lines = f.readlines()

        self.validate()
        self.statement = Statement(
            bank_id=self.bank_id,
            account_id=self.account_id,
            currency=self.currency
        )

    @property
    def reader(self):
        return csv.reader(self.lines, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)

    @property
    def header(self):
        return [c.strip() for c in head(self.reader)]

    @property
    def rows(self):
        rs = drop(self.reader, 1)
        currency_idx = self.valid_header.index("Currency")
        return [r for r in rs if r[currency_idx] == self.currency]

    def validate(self):
        """
        Validate to ensure csv has the same header we expect.
        """

        expected = self.valid_header
        actual = self.header
        if expected != actual:
            msg = "\n".join([
                "Header template doesn't match:",
                "expected: %s" % expected,
                "actual  : %s" % actual
            ])
            raise ValueError(msg)

    def split_records(self):
        for row in self.rows:
            yield row

    def parse_record(self, row):
        print(row[self.valid_header.index("Currency")])
        date_idx = self.valid_header.index("Date")
        memo_idx = self.valid_header.index("Type")
        amount_idx = self.valid_header.index("Amount")
        payee_idx = self.valid_header.index("Name")

        stmt_line = StatementLine()
        stmt_line.date = datetime.strptime(row[date_idx], self.date_format)
        stmt_line.memo = row[memo_idx]

        if self.analyze:
            memo_parts = [
                row[memo_idx]
            ]

            payee = row[payee_idx]
            # if payee and (payee.lower() == 'steamgameseu@steampowered.com'):
            #     memo_parts.append(row[title_idx])

            # stmt_line.memo = ' / '.join(filter(bool, memo_parts))

        stmt_line.amount = atof(row[amount_idx].replace(" ", ""), self.locale)
        stmt_line.payee = row[payee_idx]
        stmt_line.id = generate_transaction_id(stmt_line)

        return stmt_line


def parse_bool(value):
    if value in ('True', 'true', '1'):
        return True
    if value in ('False', 'false', '0'):
        return False
    raise ValueError("Can't parse boolean value: %s" % value)


class PayPalPlugin(Plugin):
    def get_parser(self, fin):
        kwargs = {
            'encoding': 'iso8859-1',
        }
        if self.settings:
            if 'account_id' in self.settings:
                kwargs['account_id'] = self.settings.get('account_id')
            if 'currency' in self.settings:
                kwargs['currency'] = self.settings.get('currency')
            if 'locale' in self.settings:
                kwargs['locale'] = self.settings.get('locale')
            if 'encoding' in self.settings:
                kwargs['encoding'] = self.settings.get('encoding')
            if 'analyze' in self.settings:
                kwargs['analyze'] = parse_bool(self.settings.get('analyze'))
        return PayPalStatementParser(fin, **kwargs)
