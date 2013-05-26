from __future__ import unicode_literals
from __future__ import print_function


from httpretty import HTTPretty
import json
import pytest
import re
from contextlib import contextmanager

import uritemplate

import rest_navigator.halnav as HN

# pylint: disable-msg=E1101


@contextmanager
def httprettify():
    '''Context manager to do what the @httprettified decorator does (without
    mucking up py.test's magic)

    '''
    HTTPretty.reset()
    HTTPretty.enable()
    try:
        yield HTTPretty
    finally:
        HTTPretty.disable()


def register_hal(
        uri, links=None, state=None, title=None, method='GET', headers=None):
    '''Convenience function that registers a hal document at a given address'''

    def body_callback(_meth, req_uri, req_headers):
        '''This is either registered for dynamic uris or is called for a
        static uri'''
        _links = links.copy() if links is not None else {}
        _state = state.copy() if state is not None else {}
        if headers is not None:
            resp_headers = headers.copy()
        else:
            resp_headers = {}
        if req_headers is not None:
            resp_headers.update(req_headers)
        resp_headers.update({'content_type': 'application/hal+json',
                             'server': 'HTTPretty 0.6.0'})
        _links.update({'self': {'href': req_uri}})
        if title is not None:
            _links['self']['title'] = title
        _state.update({'_links': _links})
        return 200, resp_headers, json.dumps(_state)

    HTTPretty.register_uri(method=method,
                           body=body_callback,
                           uri=uri)


def test_HALNavigator__creation():
    N = HN.HALNavigator('http://www.example.com')
    assert type(N) == HN.HALNavigator
    assert repr(N) == "HALNavigator('http://www.example.com')"


def test_HALNavigator__optional_name():
    N = HN.HALNavigator('http://www.example.com', name='exampleAPI')
    assert repr(N) == "HALNavigator('exampleAPI')"


def test_HALNavigator__links():
    with httprettify():
        register_hal('http://www.example.com/',
                     links={'ht:users': {
                         'href': 'http://www.example.com/users'}}
                     )
        N = HN.HALNavigator('http://www.example.com')
        assert N.links == {
            'ht:users': HN.HALNavigator('http://www.example.com')['ht:users']}


def test_HALNavigator__call():
    with httprettify():
        uri = 'http://www.example.com/index'
        server_state = dict(some_attribute='some value')
        register_hal(uri=uri, state=server_state, title='Example Title')

        N = HN.HALNavigator(uri)
        assert N.state is None
        assert N() == server_state
        assert N.state == N()
        assert N.state is not N()
        assert N() is not N()


def test_HALNavigator__init_accept_schemaless():
    uri = 'www.example.com'
    N = HN.HALNavigator(uri)
    assert N.uri == 'http://' + uri
    uri2 = 'http://example.com'
    N_first = HN.HALNavigator(uri2)
    assert N_first.uri == uri2


def test_HALNavigator__getitem_self_link():
    with httprettify():
        uri = 'http://www.example.com/index'
        title = 'Some kinda title'
        register_hal(uri, title=title)

        N = HN.HALNavigator(uri)
        N()  # fetch it
        assert N.title == title


def test_HALNavigator__identity_map():
    with httprettify():
        index_uri = 'http://www.example.com/'
        page1_uri = index_uri + '1'
        page2_uri = index_uri + '2'
        page3_uri = index_uri + '3'
        index_links = {'first': {'href': page1_uri}}
        page1_links = {'next': {'href': page2_uri}}
        page2_links = {'next': {'href': page3_uri}}
        page3_links = {'next': {'href': page1_uri}}

        register_hal(index_uri, index_links)
        register_hal(page1_uri, page1_links)
        register_hal(page2_uri, page2_links)
        register_hal(page3_uri, page3_links)

        N = HN.HALNavigator(index_uri)
        page1 = N['first']
        page2 = N['first']['next']
        page3 = N['first']['next']['next']
        page4 = N['first']['next']['next']['next']
        assert page1 is page4
        assert page2 is page4['next']
        assert page3 is page4['next']['next']


def test_HALNavigator__iteration():
    r'''Test that a navigator with 'next' links can be used for iteration'''
    with httprettify():
        index_uri = 'http://www.example.com/'
        index_links = {'next': {'href': index_uri + '1'}}
        register_hal(index_uri, index_links)
        for i in xrange(1, 11):
            page_uri = index_uri + str(i)
            if i < 10:
                page_links = {'next': {'href': index_uri + str(i + 1)}}
            else:
                page_links = {}
            print(page_uri, page_links)
            register_hal(page_uri, page_links)

        N = HN.HALNavigator(index_uri)
        captured = []
        for i, nav in enumerate(N, start=1):
            print('{}: {}'.format(i, nav.uri))
            assert isinstance(nav, HN.HALNavigator)
            assert nav.uri == index_uri + str(i)
            captured.append(nav)
        assert len(captured) == 10


def test_HALNavigator__expand():
    r'''Tests various aspects of template expansion'''
    with httprettify():
        index_uri = 'http://www.example.com/'
        template_uri = 'http://www.example.com/{?x,y,z}'
        index_links = {'template': {
            'href': template_uri,
            'templated': True,
        }}
        register_hal(index_uri, index_links)

        N = HN.HALNavigator(index_uri)

        unexpanded = N['template']
        unexpanded2 = N['template']
        assert unexpanded is not unexpanded2
        assert unexpanded.uri is None
        assert unexpanded.template_uri == index_links['template']['href']
        assert unexpanded.templated

        expanded = unexpanded.expand(x=1, y=2, z=3)
        expanded2 = unexpanded.expand(x=1, y=2, z=3)
        assert expanded is expanded2
        assert expanded is not unexpanded
        assert expanded.template_uri is None
        assert expanded.template_args is None
        assert expanded.uri == uritemplate.expand(
            template_uri, variables=dict(x=1, y=2, z=3))

        half_expanded = unexpanded.expand(
            _keep_templated=True, x=1, y=2)
        half_expanded2 = unexpanded.expand(
            _keep_templated=True, x=1, y=2)
        # half expanded templates don't go into the id map
        assert half_expanded is not half_expanded2
        # but they should be equivalent
        assert half_expanded == half_expanded2
        assert half_expanded.uri == uritemplate.expand(
            template_uri, variables=dict(x=1, y=2))
        assert half_expanded.template_uri == template_uri
        assert half_expanded.template_args == dict(x=1, y=2)


def test_HALNavigator__dont_get_template_links():
    with httprettify():
        index_uri = 'http://www.example.com/'
        index_regex = re.compile(index_uri + '.*')
        template_href = 'http://www.example.com/{?max,page}'
        index_links = {'first': {
            'href': template_href,
            'templated': True
        }}
        register_hal(index_regex, index_links)

        N = HN.HALNavigator(index_uri)
        with pytest.raises(TypeError):
            assert N['page': 0]  # N is not templated
        with pytest.raises(HN.exc.AmbiguousNavigationError):
            assert N['first']()  # N['first'] is templated
        assert N['first'].templated
        assert N['first']['page': 0].uri == 'http://www.example.com/?page=0'
        assert not N['first']['page':0].templated
        with pytest.raises(ValueError):
            assert N['first'][:'page':0]
        with pytest.raises(ValueError):
            assert N['first'][::'page']


def test_HALNavigator__getitem_gauntlet():
    with httprettify():
        index_uri = 'http://www.example.com/'
        index_regex = re.compile(index_uri + '.*')
        template_href = 'http://www.example.com/{?max,page}'
        index_links = {'first': {
            'href': template_href,
            'templated': True
        }}
        register_hal(index_regex, index_links)

        N = HN.HALNavigator(index_uri)
        expanded_nav = N['first', 'page':0, 'max':1]
        assert expanded_nav.uri == uritemplate.expand(template_href,
                                                      {'max': 1, 'page': '0'})
        assert N['first'].expand(page=0, max=1) == expanded_nav
        assert N['first']['page': 0].uri == uritemplate\
            .expand(template_href, {'page': '0'})
        assert N['first', :].uri == uritemplate.expand(
            template_href, variables={})

        first_page_expanded = uritemplate.expand(template_href, {'page': '0'})
        first_null_expanded = uritemplate.expand(template_href, {})
        first_both_expanded = uritemplate.expand(
            template_href, {'page': '0', 'max': 4})
        # (somewhat) exhaustive combinations
        N_first = N['first']
        with pytest.raises(TypeError):
            assert N['page': 0]
        assert N_first['page':0].uri == first_page_expanded
        assert N[...].uri == N.uri
        with pytest.raises(TypeError):
            assert N['page': 0, ...]
        assert N_first['page':0, ...].uri == first_page_expanded
        assert N_first['page':0, ...].templated
        with pytest.raises(TypeError):
            assert N[:]
        assert N_first[:].uri == first_null_expanded
        with pytest.raises(TypeError):
            assert N['page':0, :]
        assert N_first['page':0, :].uri == first_page_expanded
        assert not N_first['page':0, :].templated
        with pytest.raises(SyntaxError):
            assert N[:, ...]
        with pytest.raises(SyntaxError):
            assert N['page':0, :, ...]
        assert N['first'].template_uri == template_href
        assert N['first', 'page': 0].uri == first_page_expanded
        assert N['first', ...].template_uri == template_href
        assert N['first', 'page':0, ...].template_uri == template_href
        assert N['first', 'page':0, ...].templated
        assert N['first', 'page':0, ...]['max': 4].uri == first_both_expanded
        assert N['first', :].uri == first_null_expanded
        assert not N['first', :].templated
        assert N['first', 'page':0, :].uri == first_page_expanded
        assert not N['first', 'page':0, :].templated
        with pytest.raises(SyntaxError):
            assert N['first', :, ...]
        with pytest.raises(SyntaxError):
            assert N['first', 'page': 0, :, ...]


def test_HALNavigator__bad_getitem_objs():
    with httprettify():
        index_uri = 'http://www.example.com/'
        index_regex = re.compile(index_uri + '.*')
        template_href = 'http://www.example.com/{?max,page}'
        index_links = {'first': {
            'href': template_href,
            'templated': True
        }}
        register_hal(index_regex, index_links)

        N = HN.HALNavigator(index_uri)
        with pytest.raises(TypeError):
            N[{'set'}]
        with pytest.raises(TypeError):
            N[12]


def test_HALNavigator__double_dereference():
    with httprettify():
        index_uri = 'http://www.example.com/'
        first_uri = index_uri + '1'
        second_uri = index_uri + '2'
        index_links = {'first': {'href': first_uri}}
        first_links = {'second': {'href': second_uri}}
        second_links = {}
        register_hal(index_uri, index_links)
        register_hal(first_uri, first_links)
        register_hal(second_uri, second_links)

        N = HN.HALNavigator(index_uri)
        assert N['first', 'second'].uri == second_uri


def test_HALNavigator__parameters():
    with httprettify():
        index_uri = 'http://www.example.com/'
        index_links = {'test': {'href': 'http://{.domain*}{/a,b}{?q,r}',
                                'templated': True}}
        register_hal(index_uri, index_links)

        N = HN.HALNavigator(index_uri)
        assert N['test'].parameters == set(['a', 'b', 'q', 'r', 'domain'])
