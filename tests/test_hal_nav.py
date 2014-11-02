from __future__ import print_function

import json
import re
import contextlib
import random
import string

import httpretty
import pytest
import uritemplate

import restnavigator.halnav as HN



# pylint: disable-msg=E1101


@pytest.fixture()
def random_string():
    def rs():
        while True:
            yield ''.join(random.sample(string.ascii_letters, 6))

    return rs()


@contextlib.contextmanager
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
        next_uri = 'http://www.example.com/api/foos/123f/bars/234'
        user_uri = 'http://www.example.com/api/users/ko%C5%BEu%C5%A1%C4%8Dek'
        last_uri = 'http://www.example.com/api/last'
        register_hal(index_uri, {'first': {'href': first_uri},
                                 'next': {'href': next_uri},
                                 'last': {'href': last_uri},
                                 'describes': {'href': user_uri}})

        N_1 = HN.HALNavigator(index_uri)
        assert repr(N_1) == "HALNavigator(ExampleAPI)"
        N = HN.HALNavigator(index_uri, apiname='exampleAPI')
        assert repr(N) == "HALNavigator(exampleAPI)"
        assert repr(N['first']) == "HALNavigator(exampleAPI.first)"
        assert repr(N['next']) == \
               "HALNavigator(exampleAPI.foos.123f.bars[234])"
        assert repr(N['last']) == "HALNavigator(exampleAPI.last)"
        assert repr(N['describes']) == \
               "HALNavigator(exampleAPI.users.kozuscek)"


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
        index_links = {'first': {'href': index_uri + '1'}}
        register_hal(index_uri, index_links)
        for i in xrange(1, 11):
            page_uri = index_uri + str(i)
            if i < 10:
                page_links = {'next': {'href': index_uri + str(i + 1)}}
            else:
                page_links = {}
            register_hal(page_uri, page_links)

        N = HN.HALNavigator(index_uri)
        Nitems = N['first']
        captured = []
        for i, nav in enumerate(Nitems, start=1):
            if i == 0:
                assert nav is Nitems
            else:
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
        with pytest.raises(HN.exc.AmbiguousNavigationError):
            assert N['first'].create()  # N['first'] is templated
        with pytest.raises(HN.exc.AmbiguousNavigationError):
            assert N['first'].delete()  # N['first'] is templated

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
        assert N['first']['page': 0].uri == uritemplate \
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
        assert N2.uri == new_resource_uri
        assert not N2.fetched


@pytest.mark.parametrize(('redirect_status', 'delete_body'), [
    (202, {'name': 'foo'}),
    (302, {'name': 'foo'}),
    (303, {'name': 'foo'}),
    (303, '{"name":"foo"}'),
])
def test_HALNavigator__delete(redirect_status, delete_body):
    with httprettify() as HTTPretty:
        index_uri = 'http://www.example.com/api/'
        hosts_uri = index_uri + 'hosts'
        new_resource_uri = index_uri + 'new_resource'
        index_links = {'hosts': {'href': hosts_uri, 'method': 'DELETE'}}
        register_hal(index_uri, index_links)
        register_hal(new_resource_uri)
        HTTPretty.register_uri('DELETE',
                               uri=hosts_uri,
                               location=new_resource_uri,
                               status=redirect_status,
        )
        N = HN.HALNavigator(index_uri)
        N2 = N['hosts'].delete(delete_body)
        assert HTTPretty.last_request.method == 'DELETE'
        last_content_type = HTTPretty.last_request.headers['content-type']
        assert last_content_type == 'application/json'
        assert HTTPretty.last_request.body == '{"name":"foo"}'
        assert N2.uri == new_resource_uri
        assert not N2.fetched


@pytest.mark.parametrize(('status', 'body', 'content_type'), [
    (200, 'hi there', 'text/plain'),
    (200, '{"hi": "there"}', 'application/json'),
    (200,
     json.dumps({'_links': {'alternate': {'href': '/hogo'}},
                 "hi": "there"}), 'application/hal+json'),
    (204, '', 'text/plain'),
])
def test_OrphanResource__basic(status, body, content_type):
    with httprettify() as HTTPretty:
        index_uri = 'http://www.example.com/api/'
        hosts_uri = index_uri + 'hosts'
        index_links = {'hosts': {'href': hosts_uri}}
        register_hal(index_uri, index_links)
        HTTPretty.register_uri(
            'POST',
            uri=hosts_uri,
            status=status,
            body=body,
            content_type=content_type,
        )

        N = HN.HALNavigator(index_uri)
        N2 = N['hosts']
        OR = N2.create({})  # OR = OrphanResource

        assert isinstance(OR, HN.OrphanResource)
        assert OR.status[0] == status
        assert OR.parent is N2

        with pytest.raises(NotImplementedError):
            OR.fetch()
        with pytest.raises(NotImplementedError):
            OR.create({'values': True, 'hi': 'there'})
        if status == 200 and content_type == 'text/plain':
            assert OR.state == {}
            assert OR.response.text == 'hi there'
        elif content_type == 'application/json':
            assert OR.state == {'hi': 'there'}
        elif content_type == 'application/hal+json':
            assert 'alternate' in OR.links
            assert OR.links['alternate'].uri == 'http://www.example.com/hogo'
        elif status == 204:
            assert OR.state == {}
            assert OR.links == {}

        assert OR() == OR.state


def test_HALNavigator__relative_links():
    with httprettify():
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


def test_HALNavigator__authenticate(random_string):
    with httprettify() as HTTPretty:
        index_uri = 'http://www.example.com/api/'
        auth_uri = 'http://www.example.com/api/auth'
        index_links = {'start': {'href': auth_uri}}
        username = next(random_string)
        password = next(random_string)

        def auth_callback(r, uri, headers):
            username_ok = r.headers.get('Username') == username
            password_ok = r.headers.get('Password') == password
            if username_ok and password_ok:
                return (200, headers, json.dumps({'authenticated': True}))
            else:
                return (401, headers, json.dumps({'authenticated': False}))

        register_hal(index_uri, index_links)
        HTTPretty.register_uri('GET', auth_uri, body=auth_callback)

        def toy_auth(req):
            req.headers['Username'] = username
            req.headers['Password'] = password
            return req

        N = HN.HALNavigator(index_uri, apiname='N1', auth=toy_auth)
        assert N['start']()['authenticated']

        N2 = HN.HALNavigator(index_uri, apiname='N2', auth=None)
        N2_auth = N2['start']
        N2_auth(raise_exc=False)
        assert N2_auth.status == (401, 'Unauthorized')
        N2.authenticate(toy_auth)
        assert N2_auth.fetch()['authenticated']


def test_HALNavigator__not_json():
    '''This is a pretty common problem'''
    with httprettify() as HTTPretty:
        index_uri = 'http://www.example.com/api/'
        html = '<p>\n\tThis is not JSON\n</p>'
        HTTPretty.register_uri('GET', index_uri, body=html)

        N = HN.HALNavigator(index_uri)
        with pytest.raises(HN.UnexpectedlyNotJSON):
            N()


def test_HALNavigator__custom_headers():
    with httprettify() as HTTPretty:
        index_uri = 'http://www.example.com/'
        register_hal(index_uri, {})

        custom_headers = {'X-Pizza': 'true'}
        N = HN.HALNavigator(index_uri, headers=custom_headers)
        N()
        assert HTTPretty.last_request.headers.get('X-Pizza')


@pytest.fixture
def bigtest_1():
    bigtest = type(str('bigtest_1'), (object,), {})
    bigtest.index_uri = index_uri = 'http://www.example.com/'
    bigtest.gadget_profile = gadget = index_uri + 'profiles/gadget'
    bigtest.widget_profile = widget = index_uri + 'profiles/widget'
    bigtest.index_links = {
        'self': {'href': index_uri},
        'curies': [{'href': index_uri + 'rels/{rel}',
                    'name': 'test'}],
        'test:foo': [
            {'href': index_uri + 'bar',
             'name': 'bar',
             'title': 'Bar',
             'profile': widget,
            },
            {'href': index_uri + 'baz',
             'name': 'baz',
             'title': 'Baz',
             'profile': gadget,
            },
            {'href': index_uri + 'qux',
             'name': 'qux',
             'title': 'Qux',
             'profile': widget,
            },
        ]
    }
    return bigtest


def test_HALNavigator__get_by_properties_single(bigtest_1):
    with httprettify() as HTTPretty:
        register_hal(bigtest_1.index_uri, bigtest_1.index_links)

        N = HN.HALNavigator(bigtest_1.index_uri)
        baz = N.links['test:foo'].get_by('name', 'baz')
        bar = N.links['test:foo'].get_by('name', 'bar')
        qux = N.links['test:foo'].get_by('name', 'qux')
        not_found = N.links['test:foo'].get_by('name', 'not_found')
        assert baz.uri == bigtest_1.index_links['test:foo'][1]['href']
        assert bar.uri == bigtest_1.index_links['test:foo'][0]['href']
        assert qux.uri == bigtest_1.index_links['test:foo'][2]['href']
        assert not_found is None


def test_HALNavigator__get_by_properties_multi(bigtest_1):
    with httprettify() as HTTPretty:
        register_hal(bigtest_1.index_uri, bigtest_1.index_links)

        N = HN.HALNavigator(bigtest_1.index_uri)
        bar = N.links['test:foo'].get_by('name', 'bar')
        baz = N.links['test:foo'].get_by('name', 'baz')
        qux = N.links['test:foo'].get_by('name', 'qux')

        bazs = N.links['test:foo'].getall_by('name', 'baz')
        assert bazs == [baz]
        not_founds = N.links['test:foo'].getall_by('name', 'not_founds')
        assert not_founds == []
        widgets = N.links['test:foo'].getall_by('profile',
                                                bigtest_1.widget_profile)
        gadgets = N.links['test:foo'].getall_by('profile',
                                                bigtest_1.gadget_profile)
        assert widgets == [bar, qux]
        assert gadgets == [baz]


@pytest.fixture
def reltest_links():
    return {
        'xx:next': {
            'href': 'http://example.com/api/xxnext',
        },
        'xx:nonstandard-rel': {
            'href': 'http://example.com/api/xxnonstandard',
        },
        'yy:nonstandard-rel': {
            'href': 'http://example.com/api/yynonstandard',
        },
        'next': {
            'href': 'http://example.com/api/next',
        },
    }


def test_HALNavigator__default_curie_noconflict(reltest_links):
    with httprettify() as HTTPretty:
        index_uri = "http://example.com/api"
        register_hal(index_uri, links=reltest_links)

        N = HN.HALNavigator(index_uri, curie="xx")

        N1 = N['nonstandard-rel']
        N2 = N['xx:nonstandard-rel']

        assert N1 is N2


def test_HALNavigator__default_curie_conflict(reltest_links):
    with httprettify() as HTTPretty:
        index_uri = "http://example.com/api"
        register_hal(index_uri, links=reltest_links)

        N = HN.HALNavigator(index_uri, curie="xx")

        N1 = N['next']

        assert N1.uri == 'http://example.com/api/next'

        N2 = N['xx:next']

        assert N2.uri == 'http://example.com/api/xxnext'


def test_HALNavigator__default_curie_wrong_curie(reltest_links):
    with httprettify() as HTTPretty:
        index_uri = "http://example.com/api"
        register_hal(index_uri, links=reltest_links)

        N = HN.HALNavigator(index_uri, curie="xx")

        N1 = N['nonstandard-rel']
        N2 = N['yy:nonstandard-rel']

        assert N1 is not N2


def test_HALNavigator__default_curie_iana_conflict(reltest_links):
    with httprettify() as HTTPretty:
        index_uri = "http://example.com/api"
        del reltest_links['next']
        register_hal(index_uri, links=reltest_links)

        N = HN.HALNavigator(index_uri, curie="xx")

        assert N['next'] is N['xx:next']
