from __future__ import unicode_literals
from __future__ import print_function


import httpretty
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
    httpretty.HTTPretty.reset()
    httpretty.HTTPretty.enable()
    try:
        yield httpretty.HTTPretty
    finally:
        httpretty.HTTPretty.disable()


def register_hal(uri='http://www.example.com/',
                 links=None,
                 state=None,
                 title=None,
                 method='GET',
                 headers=None,
                 status=200,
                 ):
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
        return status, resp_headers, json.dumps(_state)

    httpretty.HTTPretty.register_uri(method=method,
                                     body=body_callback,
                                     uri=uri)


def test_HALNavigator__creation():
    N = HN.HALNavigator('http://www.example.com')
    assert type(N) == HN.HALNavigator
    assert repr(N) == "HALNavigator(Example)"


@pytest.mark.parametrize(('name1', 'uri1', 'name2', 'uri2', 'equal'), [
    ('apiname', 'http://www.aaa.com', 'apiname', 'http://www.bbb.com', False),
    ('api1', 'http://www.bbb.com', 'api2', 'http://www.bbb.com', False),
    ('api1', 'http://www.aaa.com', 'api1', 'http://www.aaa.com', True),
])
def test_HALNavigator__eq__(name1, uri1, name2, uri2, equal):
    N1 = HN.HALNavigator(uri1, apiname=name1)
    N2 = HN.HALNavigator(uri2, apiname=name2)
    if equal:
        assert N1 == N2
        assert N2 == N1
    else:
        assert N1 != N2
        assert N2 != N1


def test_HALNavigator__eq__nonnav():
    N = HN.HALNavigator('http://www.example.com')
    assert N != 'http://www.example.com'
    assert 'http://www.example.com' != N


def test_HALNAvigator__repr():
    with httprettify():
        index_uri = 'http://www.example.com/api/'
        first_uri = 'http://www.example.com/api/first'
        next_uri = 'http://www.example.com/api/foos/123/bars/234'
        last_uri = 'http://www.example.com/api/last'
        register_hal(index_uri, {'first': {'href': first_uri},
                                 'next': {'href': next_uri},
                                 'last': {'href': last_uri}})

        N_1 = HN.HALNavigator(index_uri)
        assert repr(N_1) == "HALNavigator(ExampleAPI)"
        N = HN.HALNavigator(index_uri, apiname='exampleAPI')
        assert repr(N) == "HALNavigator(exampleAPI)"
        assert repr(N['first']) == "HALNavigator(exampleAPI.first)"
        assert repr(N['next']) == \
          "HALNavigator(exampleAPI.foos[123].bars[234])"
        assert repr(N['last']) == "HALNavigator(exampleAPI.last)"


def test_HALNavigator__links():
    with httprettify():
        register_hal('http://www.example.com/',
                     links={'ht:users': {
                         'href': 'http://www.example.com/users'}}
                     )
        N = HN.HALNavigator('http://www.example.com')
        expected = {
            'ht:users': HN.HALNavigator('http://www.example.com')['ht:users']
        }
        assert N.links == expected


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
        index_links = {'about': {'href': 'http://{.domain*}{/a,b}{?q,r}',
                                 'templated': True}}
        register_hal(index_uri, index_links)

        N = HN.HALNavigator(index_uri)
        assert N['about'].parameters == set(['a', 'b', 'q', 'r', 'domain'])


@pytest.mark.parametrize(('status', 'reason'), [
    (200, 'OK'),
    (201, 'Created'),
    (303, 'See Other'),
])
def test_HALNavigator__status(status, reason):
    with httprettify():
        index_uri = 'http://www.example.com/'
        register_hal(index_uri, status=status)

        N = HN.HALNavigator(index_uri)
        assert N.status is None
        N()
        assert N.status == (status, reason)


@pytest.mark.parametrize(('status', 'raise_exc'), [
    (400, False),
    (500, False),
    (404, True),
    (503, True),
])
def test_HALNavigator__raise_exc(status, raise_exc):
    with httprettify():
        index_uri = 'http://www.example.com/'
        next_uri = index_uri + 'next'
        index_links = {'next': {'href': next_uri}}
        register_hal(index_uri, index_links)
        register_hal(next_uri, status=status)

        N = HN.HALNavigator('http://www.example.com/')
        if raise_exc:
            with pytest.raises(HN.HALNavigatorError):
                N['next']()
            try:
                N['next'].fetch()
            except HN.HALNavigatorError as hn:
                assert hn.nav.status[0] == status
        else:
            N['next'](raise_exc=False)
            assert N['next'].status[0] == status


@pytest.mark.parametrize(('status', 'boolean'), [
    (200, True),
    (300, True),
    (400, False),
    (500, False),
])
def test_HALNavigator__boolean(status, boolean):
    with httprettify():
        register_hal(status=status)

        N = HN.HALNavigator('http://www.example.com/')
        if boolean:
            assert N
        else:
            assert not N


def test_HALNavigator__boolean_fetched():
    with httprettify():
        register_hal(status=200)

        N = HN.HALNavigator('http://www.example.com/')
        N()
        assert N

        register_hal(status=500)
        N = HN.HALNavigator('http://www.example.com/')
        N(raise_exc=False)
        assert not N


def test_HALNavigator__multiple_links():
    with httprettify():
        index_uri = 'http://www.example.com/'
        index_links = {
            'about': {
                'href': index_uri + 'about',
                'title': 'A single link',
            },
            'alternate': [{'href': index_uri + 'alt/' + str(i),
                           'name': 'alt_' + str(i)}
                          for i in xrange(5)]
        }
        register_hal(index_uri, index_links)

        N = HN.HALNavigator(index_uri)
        assert isinstance(N['about'], HN.HALNavigator)
        assert isinstance(N['alternate'], list)
        for i, n in enumerate(N['alternate']):
            assert isinstance(n, HN.HALNavigator)
            assert n.uri == index_links['alternate'][i]['href']
        assert len(N['alternate']) == 5


def test_HALNavigator__multilink_gauntlet():
    with httprettify():
        index_uri = 'http://www.example.com/api/'
        first_uri = index_uri + 'first'
        second_a_uri = index_uri + 'second/a'
        second_b_uri = index_uri + 'second/b'
        third_uri = index_uri + 'third/{keyword}'
        index_links = {'first': {'href': first_uri}}
        first_links = {'next': [{'href': second_a_uri},
                                {'href': second_b_uri}]}
        second_links = {'next': [{'href': third_uri, 'templated': True}]}
        register_hal(index_uri, index_links)
        register_hal(first_uri, first_links)
        register_hal(second_a_uri, second_links)
        register_hal(second_b_uri, second_links)
        register_hal(third_uri, index_links)

        N = HN.HALNavigator(index_uri)
        N_1 = N['first']
        N_2a = N['first', 'next'][0]
        N_2b = N['first', 'next'][1]
        N_3a = N['first', 'next'][0]['next']
        N_3b = N['first', 'next'][1]['next']
        N_3_completed = N['first', 'next'][0]['next', 'keyword':'foo']
        assert N_1.uri == first_uri
        assert N_2a.uri == second_a_uri
        assert N_2b.uri == second_b_uri
        assert N_3a.templated and N_3a.template_uri == third_uri
        assert N_3b.templated and N_3b.template_uri == third_uri
        assert N_3a == N_3b
        assert N_3_completed.uri == 'http://www.example.com/api/third/foo'


def test_HALNavigator__relative_link():
    with httprettify():
        index_uri = 'http://www.example.com/api/'
        relative_uri = 'another/link'
        relative_templated = 'another/{link}'
        index_links = {
            'alternate': [{'href': index_uri + relative_uri},
                          {'href': index_uri + relative_templated,
                           'templated': True}],
        }
        register_hal(index_uri, index_links)
        N = HN.HALNavigator(index_uri)
        assert N['alternate'][0].relative_uri == '/' + relative_uri
        assert N['alternate'][1].relative_uri == '/' + relative_templated


def test_HALNavigator__fetch():
    with httprettify() as HTTPretty:
        index_uri = r'http://www.example.com'
        index_re = re.compile(index_uri)
        index_links = {'self': {'href': index_uri}}
        body1 = {'name': 'body1', '_links': index_links}
        body2 = {'name': 'body2', '_links': index_links}
        responses = [httpretty.Response(body=json.dumps(body1)),
                     httpretty.Response(body=json.dumps(body2))]
        HTTPretty.register_uri(method='GET',
                               uri=index_re,
                               headers={'content_type': 'application/hal+json',
                                        'server': 'HTTPretty 0.6.0'},
                               responses=responses)
        N = HN.HALNavigator(index_uri)
        fetch1 = N()
        fetch2 = N()
        fetch3 = N.fetch()
        assert fetch1['name'] == 'body1'
        assert fetch2['name'] == 'body1'
        assert fetch3['name'] == 'body2'


@pytest.mark.parametrize(('redirect_status', 'post_body'), [
    (302, {'name': 'foo'}),
    (303, {'name': 'foo'}),
    (204, {'name': 'foo'}),
    (201, {'name': 'foo'}),
    (202, {'name': 'foo'}),
    (303, '{"name":"foo"}'),
])
def test_HALNavigator__create(redirect_status, post_body):
    with httprettify() as HTTPretty:
        index_uri = 'http://www.example.com/api/'
        hosts_uri = index_uri + 'hosts'
        new_resource_uri = index_uri + 'new_resource'
        index_links = {'hosts': {'href': hosts_uri}}
        register_hal(index_uri, index_links)
        register_hal(new_resource_uri)
        HTTPretty.register_uri('POST',
                               uri=hosts_uri,
                               location=new_resource_uri,
                               status=redirect_status,
                               )
        N = HN.HALNavigator(index_uri)
        N2 = N['hosts'].create(post_body)
        assert HTTPretty.last_request.method == 'POST'
        last_content_type = HTTPretty.last_request.headers['content-type']
        assert last_content_type == 'application/json'
        assert HTTPretty.last_request.body == '{"name":"foo"}'
        if redirect_status in (201, 202, 302, 303):
            assert N2.uri == new_resource_uri
            assert not N2.fetched
        else:
            assert N2[0] == redirect_status
            assert N2[1].headers['location'] == new_resource_uri


def test_HALNavigator__relative_links():
    with httprettify() as HTTPretty:
        index_uri = 'http://www.example.com/'
        about_relative_uri = '/about/'
        about_full_uri = index_uri + 'about/'
        index_links = {'about': {'href': about_relative_uri}}
        about_links = {'alternate': {'href': 'alternate'},
                       'index': {'href': './index'}}
        register_hal(index_uri, index_links)
        register_hal(about_full_uri, about_links)

        N = HN.HALNavigator(index_uri)
        assert N['about'].uri == 'http://www.example.com/about/'
        assert N['about', 'alternate'].uri == \
            'http://www.example.com/about/alternate'
        assert N['about']['index'].uri == 'http://www.example.com/about/index'
