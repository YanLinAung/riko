# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:expandtab
"""
    pipe2py.modules.pipeexchangerate
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import requests

from itertools import imap
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.threads import deferToThread
from . import get_broadcast_funcs as get_funcs
from pipe2py.lib import utils
from pipe2py.lib.dotdict import DotDict
from pipe2py.twisted.utils import asyncGather

timeout = 60 * 60 * 24  # 24 hours in seconds

FIELDS = [
    {'name': 'USD/USD', 'price': 1},
    {'name': 'USD/EUR', 'price': 0.8234},
    {'name': 'USD/GBP', 'price': 0.6448},
    {'name': 'USD/INR', 'price': 63.6810},
]

EXCHANGE_API_BASE = 'http://finance.yahoo.com/webservice'
EXCHANGE_API = '%s/v1/symbols/allcurrencies/quote' % EXCHANGE_API_BASE
PARAMS = {'format': 'json'}


# Common functions
def get_parsed(_INPUT, conf, **kwargs):
    inputs = imap(DotDict, _INPUT)
    broadcast_funcs = get_funcs(conf, listize=False, **kwargs)
    dispatch_funcs = [utils.passthrough, utils.get_word, utils.passthrough]
    splits = utils.broadcast(inputs, *broadcast_funcs)
    return utils.dispatch(splits, *dispatch_funcs)


def get_base(conf, word):
    base = word or conf.default

    try:
        offline = conf.offline
    except AttributeError:
        offline = False

    return (base, offline)


def calc_rate(from_cur, to_cur, rates):
    if from_cur == to_cur:
        rate = 1
    elif to_cur == 'USD':
        rate = rates['USD/%s' % from_cur]
    else:
        usd_to_given = rates['USD/%s' % from_cur]
        usd_to_default = rates['USD/%s' % to_cur]
        rate = usd_to_given * (1 / usd_to_default)

    return 1 / float(rate)


def parse_request(r, offline):
    if offline:
        fields = FIELDS
    else:
        resources = r['list']['resources']
        fields = (r['resource']['fields'] for r in resources)

    return {i['name']: i['price'] for i in fields}


@utils.memoize(timeout)
def get_rate_data():
    return requests.get(EXCHANGE_API, params=PARAMS)


# Async functions
@inlineCallbacks
def asyncParseResult(conf, word, _pass):
    base, offline = get_base(conf, word)

    if offline:
        r = None
    else:
        data = yield deferToThread(get_rate_data)
        r = data.json()

    rates = parse_request(r, offline)
    result = base if _pass else calc_rate(base, conf.quote, rates)
    returnValue(result)


@inlineCallbacks
def asyncPipeExchangerate(context=None, _INPUT=None, conf=None, **kwargs):
    """A string module that asynchronously retrieves the current exchange rate
    for a given currency pair. Loopable.

    Parameters
    ----------
    context : pipe2py.Context object
    _INPUT : twisted Deferred iterable of items or strings (base currency)
    conf : {
        'quote': {'value': <'USD'>},
        'default': {'value': <'USD'>},
        'offline': {'type': 'bool', 'value': '0'},
    }

    Returns
    -------
    _OUTPUT : twisted.internet.defer.Deferred generator of hashed strings
    """
    _input = yield _INPUT
    parsed = get_parsed(_input, conf, **kwargs)
    _OUTPUT = yield asyncGather(parsed, asyncParseResult)
    returnValue(iter(_OUTPUT))


# Synchronous functions
def parse_result(conf, word, _pass):
    base, offline = get_base(conf, word)
    r = None if offline else get_rate_data().json()
    rates = parse_request(r, offline)
    result = base if _pass else calc_rate(base, conf.quote, rates)
    return result


def pipe_exchangerate(context=None, _INPUT=None, conf=None, **kwargs):
    """A string module that retrieves the current exchange rate for a given
    currency pair. Loopable.

    Parameters
    ----------
    context : pipe2py.Context object
    _INPUT : iterable of items or strings (base currency)
    conf : {
        'quote': {'value': <'USD'>},
        'default': {'value': <'USD'>},
        'offline': {'type': 'bool', 'value': '0'},
    }

    Returns
    -------
    _OUTPUT : generator of hashed strings
    """
    parsed = get_parsed(_INPUT, conf, **kwargs)
    _OUTPUT = utils.gather(parsed, parse_result)
    return _OUTPUT
