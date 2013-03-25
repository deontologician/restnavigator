from __future__ import unicode_literals
from __future__ import print_function


from httpretty import HTTPretty, httprettified
import json
import mock
import pytest
from contextlib import contextmanager

import rest_navigator as RN

@contextmanager
def httprettify():
    '''Context manager to do what the @httprettified decorator does (without mucking
    up py.test's magic)

    '''
    HTTPretty.reset()
    HTTPretty.enable()
    try:
        yield HTTPretty
    finally:
        HTTPretty.disable()


@pytest.fixture()
def requests(monkeypatch):
    m = mock.create_autospec(RN.requests)
    monkeypatch.setattr(RN, 'requests', m)
    return m

def test_Navigator__creation():
    N = RN.Navigator('http://haltalk.herokuapp.com')
    assert type(N) == RN.Navigator
    assert repr(N) == "Navigator('http://haltalk.herokuapp.com')"


def test_Navigator__optional_name():
    N = RN.Navigator('http://haltalk.herokuapp.com', name='haltalk')
    assert repr(N) == "Navigator('haltalk')"


def test_Navigator__links():
    with httprettify() as HTTPretty:
        HTTPretty.register_uri(HTTPretty.GET, 'http://haltalk.herokuapp.com/',
                               body=json.dumps({
                                   '_links': {
                                       'ht:users': {
                                           'href': 'http://haltalk.herokuapp.com/users'
                                       }
                                   }
                               }))
    
        N = RN.Navigator('http://haltalk.herokuapp.com')
        assert N.links == {'ht:users':
                           RN.Navigator('http://haltalk.herokuapp.com')['ht:users']}
    
