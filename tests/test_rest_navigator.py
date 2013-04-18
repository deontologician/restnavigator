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


def register_hal(url, links=None, state=None, title=None, method='GET'):
    '''Convenience function that registers a hal document at a given address'''
    links = links.copy() if links is not None else {}
    state = state.copy() if state is not None else {}
    links.update({'self': {'href': url}})
    if title is not None:
        links['self']['title'] = title
    state.update({'_links': links})
    HTTPretty.register_uri(method=method,
                           body=json.dumps(state),
                           content_type='application/hal+json',
                           uri=url)


def test_fix_scheme():
    assert RN.fix_scheme('http://www.example.com') == 'http://www.example.com'
    assert RN.fix_scheme('www.example.com') == 'http://www.example.com'
    with pytest.raises(ValueError):
        RN.fix_scheme('ftp://www.example.com')
    with pytest.raises(ValueError):
        RN.fix_scheme('http://http://www.example.com')


def test_Navigator__creation():
    N = RN.Navigator('http://www.example.com')
    assert type(N) == RN.Navigator
    assert repr(N) == "Navigator('http://www.example.com')"


def test_Navigator__optional_name():
    N = RN.Navigator('http://www.example.com', name='exampleAPI')
    assert repr(N) == "Navigator('exampleAPI')"


def test_Navigator__links():
    with httprettify():
        register_hal('http://www.example.com/',
                     links={'ht:users': {'href': 'http://www.example.com/users'}})
        N = RN.Navigator('http://www.example.com')
        assert N.links == {'ht:users':
                           RN.Navigator('http://www.example.com')['ht:users']}

def test_Navigator__call():
    with httprettify():
        url = 'http://www.example.com/index'
        server_state = dict(some_attribute='some value')
        register_hal(url=url, state=server_state, title='Example Title')

        N = RN.Navigator(url)
        assert N.state is None
        assert N() == server_state
        assert N.state == N()
        assert N.state is not N()
        assert N() is not N()

def test_Navigator__init_accept_schemaless():
    url = 'www.example.com'
    N = RN.Navigator(url)
    assert N.url == 'http://' + url
    url2 = 'http://example.com'
    N2 = RN.Navigator(url2)
    assert N2.url == url2

def test_Navigator__getitem_self_link():
    with httprettify():
        url = 'http://www.example.com/index'
        title = 'Some kinda title'
        register_hal(url, title=title)

        N = RN.Navigator(url)
        N()  # fetch it
        assert N.title == title


def test_Navigator__identity_map():
    with httprettify():
        index_url = 'http://www.example.com/'
        page1_url = index_url + '1'
        page2_url = index_url + '2'
        page3_url = index_url + '3'
        index_links = {'first': {'href': page1_url}}
        page1_links = {'next': {'href': page2_url}}
        page2_links = {'next': {'href': page3_url}}
        page3_links = {'next': {'href': page1_url}}

        register_hal(index_url, index_links)
        register_hal(page1_url, page1_links)
        register_hal(page2_url, page2_links)
        register_hal(page3_url, page3_links)

        N = RN.Navigator(index_url)
        page1 = N['first']
        page2 = N['first']['next']
        page3 = N['first']['next']['next']
        page4 = N['first']['next']['next']['next']
        assert page1 is page4
        assert page2 is page4['next']
        assert page3 is page4['next']['next']

def test_Navigator__iteration():
    with httprettify():
        index_url = 'http://www.example.com/'
        index_links = {'next': {'href': index_url + '1'}}
        register_hal(index_url, index_links)
        for i in xrange(1, 11):
            page_url = index_url + str(i)
            if i < 10:
                page_links = {'next': {'href': index_url + str(i + 1)}}
            else:
                page_links = {}
            print(page_url, page_links)
            register_hal(page_url, page_links)

        N = RN.Navigator(index_url)
        captured = []
        for i, nav in enumerate(N, start=1):
            print('{}: {}'.format(i, nav.url))
            assert isinstance(nav, RN.Navigator)
            assert nav.url == index_url + str(i)
            captured.append(nav)
        assert len(captured) == 10
