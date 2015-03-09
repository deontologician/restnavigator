'''Refactored tests from test_hal_nav.py'''

import json

import httpretty
import pytest

import conftest

import uritemplate

import restnavigator as RN
from restnavigator import exc
import restnavigator.halnav as HN


def uri_of(doc):
    '''Pull out the url from a hal document'''
    return doc['_links']['self']['href']

def link_to(doc):
    '''Pull out the self link of a hal document'''
    return doc['_links']['self']


def register_hal_page(doc, **kwargs):
    status = kwargs.pop('status', 200)
    method = kwargs.pop('method', 'GET')
    content_type = kwargs.pop('content_type', 'application/hal+json')
    def body_callback(request, url, headers):
        '''We do a callback so the response body can be updated'''
        headers2 = kwargs.pop('headers', headers)
        return (
            status,
            headers2,
            json.dumps(doc),
        )

    httpretty.HTTPretty.register_uri(
        method,
        body=body_callback,
        content_type=content_type,
        uri=uri_of(doc),
        **kwargs
    )

@pytest.fixture
def page(index_page, curie_links, index_uri):
    '''Returns a function that creates pages'''
    def _page(name, number):
        selflink = {
            'href': index_uri + name + '/' + str(number),
            'name': name + str(number),
        }
        nextlink =  {
            'href': index_uri + name + '/' + str(number + 1),
            'name': name + str(number + 1),
        }
        doc = {
            '_links': {
                'self': selflink,
                'curies': curie_links,
                'next': nextlink
            },
            'name': name,
            'number': number,
            'data': conftest.random_sentence(),
        }
        register_hal_page(doc)
        _page.registry.setdefault(name, []).append(doc)
        return doc
    _page.registry = {}
    return _page


@pytest.yield_fixture
def http(request):
    '''Enables httpretty and disables it after the test'''
    httpretty.HTTPretty.enable()
    yield httpretty.HTTPretty
    httpretty.HTTPretty.disable()
    httpretty.HTTPretty.reset()


@pytest.fixture
def index_uri():
    '''Fixture for the root uri'''
    return 'http://fakeuri.example/api/'

@pytest.fixture
def curie():
    '''Returns the current curie string'''
    return conftest.random_word(2).lower()

@pytest.fixture
def curify(curie):
    def _curify(rel):
        return curie + ':' + rel
    return _curify

@pytest.fixture
def curie_links(curie, index_uri):
    '''Returns a templated curie link'''
    return [{
        'name': curie,
        'href': index_uri + 'rels/{rel}',
        'templated': True,
    }]

@pytest.fixture
def index_page(curie_links, index_uri, http):
    '''Registers a basic index page that can be extended'''
    doc = {
        '_links': {
            'curies': curie_links,
            'self': {'href': index_uri},
        },
        'data': conftest.random_paragraphs(),
    }
    register_hal_page(doc)
    return doc


@pytest.fixture
def N(index_uri, index_page):
    '''A basic HALNavigator with the index_uri as root'''
    return RN.Navigator.hal(index_uri)


class TestTemplateThunk:
    '''tests for halnav.TemplatedThunk'''

    @pytest.fixture
    def rel(self, curify, name):
        '''The link relation for the templated link'''
        return curify(name)

    @pytest.fixture(params=[set(['x']), set(['x', 'y']), set(['x', 'y', 'z'])])
    def vars(self, request):
        '''A set of random variables'''
        return request.param

    @pytest.fixture(params=[(0,0,0), (1,2,3)])
    def values(self, request):
        return dict(zip('xyz', request.param))

    @pytest.fixture
    def name(self):
        '''The name of the templated resource'''
        return conftest.random_word(5).lower() + 's'

    @pytest.fixture
    def post_template(self, name, index_uri, index_page, rel, vars):
        '''Creates and registers a post templated link'''
        href = "{index_uri}{name}/{{{varpath}}}".format(
            index_uri=index_uri,
            name=name,
            varpath='}/{'.join(v for v in sorted(vars))
        )
        link = {
            'href': href,
            'title': 'Templated link for ' + name,
            'templated': True,
        }
        index_page['_links'][rel] = link
        return href

    @pytest.fixture
    def tpl_rel(self, name, curify):
        return curify(name + '_tpl')

    @pytest.fixture
    def posts(self, rel, name, index_uri, index_page, page, tpl_rel):
        '''Creates and registers some posts'''
        resource0 = page(name, 0)
        index_page['_links'][rel] = link_to(resource0)
        index_page['_links'][tpl_rel] = {
            'href': index_uri + name + '/{id}',
            'title': 'Template for ' + name,
            'templated': True,
        }
        register_hal_page(resource0)
        last = resource0
        for i in range(1, 5):
            resource = page(name, i)
            last['_links']['next'] = link_to(resource)
            last = resource
            register_hal_page(resource)
        return page.registry[name][:]

    @pytest.fixture
    def template_thunk(self, rel, index_page, N, post_template):
        return N[rel]

    def test_template_uri(self, template_thunk, post_template):
        assert template_thunk.template_uri == post_template

    def test_expand_uri(
            self, vars, post_template, template_thunk, values):
        uri = template_thunk.expand_uri(**values)
        assert uri == uritemplate.expand(post_template, values)

    def test_expand_link(
            self, vars, post_template, template_thunk, values):
        link = template_thunk.expand_link(**values)
        assert not link.props.get('templated', False)
        assert link.uri == uritemplate.expand(post_template, values)

    def test_expand(self, vars, post_template, template_thunk, values):
        post1 = template_thunk(**values)
        assert not post1.fetched
        assert post1.uri == uritemplate.expand(post_template, values)

    def test_variables(self, template_thunk, vars):
        assert template_thunk.variables == vars

    @pytest.mark.parametrize('i', range(0, 5))
    def test_valid_expansion(self, posts, name, N, tpl_rel, i):
        thunk = N[tpl_rel]
        nav = thunk(id=i)
        nav.fetch()
        assert nav.status == (200, 'OK')
        assert nav.uri == uri_of(posts[i])


class TestHALNavGetItem:
    '''Tests the __getitem__ method of HALNavigator '''

    @pytest.fixture
    def names(self):
        namelist = [conftest.random_word().lower() for _ in range(3)]
        def _names(i):
            return namelist[i]
        return _names

    @pytest.fixture
    def rels(self, names, curify):
        def _rels(i):
            return curify(names(i))
        return _rels

    @pytest.fixture
    def resources(self, names, rels, index_page, index_uri, page):
        last = index_page
        for i in range(3):
            new = page(names(i), i)
            last['_links'][rels(i)] = {
                'href': uri_of(new),
                'title': "Page for " + names(i)
            }
            last = new

    def test_fetch_behavior(self, N, resources, rels):
        Na = N[rels(0)]
        Nb = N[rels(0), rels(1)]
        assert Na.fetched
        assert not Nb.fetched

    def test_sequence_equivalence(self, N, resources, rels):
        Na = N[rels(0), rels(1), rels(2)]
        Nb = N[rels(0)][rels(1)][rels(2)]
        assert Na is Nb

    @pytest.fixture
    def link_resources(self, rels, names, index_page, page):
        first = page(names(0), 1)
        index_page['_links'][rels(0)] = link_to(first)
        register_hal_page(first)
        second1 = page(names(1), 1)
        second2 = page(names(1), 2)
        first['_links'][rels(1)] = [
            {
                'href': uri_of(second1),
                'name': 'name_x',
            },{
                'href': uri_of(second2),
                'name': 'name_y',
            }
        ]
        register_hal_page(second1)
        register_hal_page(second2)
        third_1 = page(names(2), 1)
        third_2 = page(names(2), 2)
        second1['_links'][rels(2)] = link_to(third_1)
        second2['_links'][rels(2)] = link_to(third_2)
        register_hal_page(third_1)
        register_hal_page(third_2)

    def test_linklist_in_sequence(self, N, link_resources, rels):
        Nchained = N[rels(0), rels(1), 'name':'name_x', rels(2)]
        Nfirst = N[rels(0)]
        Nsecondlist = Nfirst[rels(1)]
        Nsecond = Nsecondlist.get_by('name', 'name_x')
        Nthird = Nsecond[rels(2)]

        assert Nchained is Nthird

    def test_linklist_index(self, N, link_resources, rels):
        Nchained = N[rels(0), rels(1), 1, rels(2)]
        Nfirst = N[rels(0)]
        Nsecondlist = Nfirst[rels(1)]
        Nsecond = Nsecondlist[1]
        Nthird = Nsecond[rels(2)]
        assert Nchained is Nthird

    def test_bad_rel(self, N, link_resources, rels):
        with pytest.raises(exc.OffTheRailsException):
            N[rels(1)]

        with pytest.raises(exc.OffTheRailsException):
            N[rels(0), rels(0)]

    def test_bad_name(self, N, link_resources, rels):
        with pytest.raises(exc.OffTheRailsException):
            N[rels(0), rels(1), 'name':'badname']

    def test_bad_index(self, N, link_resources, rels):
        with pytest.raises(exc.OffTheRailsException):
            N[rels(0), rels(1), 100]

    @pytest.fixture
    def template_uri(self, index_uri):
        return index_uri + 'tpl/{id}'

    @pytest.fixture
    def tpl_rel(self, curify):
        return curify('tpl')

    @pytest.fixture
    def tpl_resources(self, page, tpl_rel, template_uri, index_page):
        index_page['_links'][tpl_rel] = {
            'href': template_uri,
            'templated': True,
            'title': 'Template link',
        }
        for i in range(3):
            resource = page('tpl', i)
            register_hal_page(resource)
        return template_uri

    def test_template_sequence(self, N, tpl_resources, tpl_rel):
        Na = N[tpl_rel](id=0)
        Nb = N[tpl_rel](id=1)
        Nc = N[tpl_rel](id=2)
        Na(), Nb(), Nc()
        assert Na.status == (200, 'OK')
        assert Nb.status == (200, 'OK')
        assert Nc.status == (200, 'OK')


class TestEmbedded:
    '''tests for embedded document features'''

    @pytest.fixture
    def blog_posts(self, http, page):
        '''Posts are both linked and embedded'''
        _posts = [page('post', x) for x in range(3)]
        for post in _posts:
            register_hal_page(post)
        return _posts

    @pytest.fixture
    def comments(self, page):
        '''Comments are embedded only and have no self link'''
        comments = [page('comments', x) for x in range(3)]
        for comment in comments:
            del comment['_links']['self']
        return comments

    @pytest.fixture
    def nested(self, page):
        '''Nested are several layers deep embedded docs. They are not
        linked to, but do have urls.
        '''
        nested = [page('nested', n) for n in range(3)]
        for (nest1, nest2) in zip(nested[:-1], nested[1:]):
            nest1['_embedded'] = {
                'xx:nested': nest2
            }
            register_hal_page(nest1)
        register_hal_page(nest2) # register remaining page
        return nested

    @pytest.fixture
    def index(self, index_uri, comments, blog_posts, http, nested):
        doc = {
            '_links': {
                'curies': [{
                    'name': 'xx',
                    'href': index_uri + 'rels/{rel}',
                    'templated': True,
                }],
                'self': {'href': index_uri},
                'first': link_to(blog_posts[0]),
                'xx:second': link_to(blog_posts[1]),
                'xx:posts': [link_to(post) for post in blog_posts],
                'xx:nested-links': [link_to(nest) for nest in nested],
                'xx:non-embedded-nest': link_to(nested[0]),
            },
            'data': 'Some data here',
            '_embedded': {
                'xx:posts': blog_posts,
                'xx:comments': comments,
            }
        }
        register_hal_page(doc)
        return doc

    def test_comments_are_orphans(self, N, index):
        '''Checks that all embedded documents that don't have self
        links are OrphanHALNavigators
        '''
        comments = N['xx:comments']
        for comment in comments:
            assert comment.parent is N

    def test_posts_arent_orphans(self, N, index):
        posts = N['xx:posts']
        for i, post in enumerate(posts):
            href = index['_embedded']['xx:posts'][i]['_links']['self']['href']
            assert post.uri == href

    def test_length_accurate(self, N, index, comments):
        assert len(N['xx:comments']) == len(comments)

    def test_embedded_only_rel_in_navigator(self, N, index):
        N.fetch()
        assert 'xx:comments' in N

    def test_embedded_only_rel_not_in_links(self, N, index):
        assert 'xx:comments' not in N.links()

    def test_embedded_only_rel_in_embedded(self, N, index):
        assert 'xx:comments' in N.embedded()

    def test_both_rel_in_navigator(self, N, index):
        N.fetch()
        assert 'xx:posts' in N

    def test_both_rel_in_links(self, N, index):
        assert 'xx:posts' in N.links()

    def test_both_rel_in_embedded(self, N, index):
        assert 'xx:posts' in N.embedded()

    def test_embedded_default_curie(self, N, index):
        N._core.default_curie = 'xx'
        p1 = N['posts']
        assert p1 is N['xx:posts']

    def test_nested_works(self, N, index, nested):
        nest1 = N['xx:non-embedded-nest']
        nest2 = nest1['xx:nested']
        nest3 = nest2['xx:nested']

        nest3_chained = N['xx:non-embedded-nest', 'xx:nested', 'xx:nested']
        assert nest3 is nest3_chained

    def test_fetch_then_get_embedded(self, N, index):
        # for this test, nested[0] is linked from index, but not
        # embedded anywhere. nested[1] is embedded in nested[0], but
        # is also its own resource. We want to ensure the same
        # navigator object is used for both
        nested1 = N['xx:nested-links'][1]
        nested1.fetch()
        assert N['xx:non-embedded-nest', 'xx:nested'] is nested1

    def test_get_embedded_then_fetch(self, N, index):
        # reverse order of previous test
        nested1 = N['xx:non-embedded-nest', 'xx:nested']
        nested1_linked = N['xx:nested-links'][1]
        # Nothing we've done to nested1_linked should have resolved it
        # except that we already saw it as an embedded doc.
        assert nested1_linked.resolved
        assert nested1 is nested1_linked


class TestCreate:

    @pytest.fixture
    def new_resource(self, page):
        grelp = page('grelp', 0)
        register_hal_page(grelp)
        return grelp

    @pytest.fixture(params=[302, 303, 202, 202, 303])
    def post_status(self, request):
        return request.param

    @pytest.fixture
    def hosts(self, page, http, post_status, new_resource):
        host_page = page('hosts', 0)
        register_hal_page(
            host_page,
            method='POST',
            status=post_status,
            location=uri_of(new_resource),
        )
        return host_page

    @pytest.fixture
    def index(self, hosts, index_uri):
        doc = {
            '_links': {
                'self': {'href': index_uri},
                'xx:create-hosts': link_to(hosts),
            }
        }
        register_hal_page(doc)
        return doc

    def test_uses_post(self, N, index, http):
        N['xx:create-hosts'].create({'name': 'foo'})
        last_request_method = http.last_request.method
        assert last_request_method == 'POST'

    def test_content_type_json(self, N, index, http):
        N['xx:create-hosts'].create({'name': 'foo'})
        last_content_type = http.last_request.headers['Content-Type']
        assert last_content_type == 'application/json'

    def test_body_is_correct(self, N, index, http):
        N['xx:create-hosts'].create({'name': 'foo'})
        last_body = http.last_request.body
        last_body == b'{"name": "foo"}'

    def test_new_resource_uri_correct(
            self, N, index, new_resource, post_status):
        N2 = N['xx:create-hosts']
        N3 = N2.create({'name': 'foo'})
        if post_status == 202:
            assert N3.parent.uri == N2.uri
            assert N3.fetched
        else:
            assert N3.uri == uri_of(new_resource)
            assert not N3.fetched

    def test_headers_passed(self, N, index, http):
        headers = {'X-Custom': 'foo'}
        N['xx:create-hosts'].create({'name': 'foo'}, headers=headers)
        custom_header = http.last_request.headers['X-Custom']
        assert custom_header == 'foo'

    def test_empty_post(self, N, index):
        # Just want to ensure no error is thrown
        N['xx:create-hosts'].create()
