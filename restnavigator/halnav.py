'''A library to allow navigating rest apis easy.'''

from __future__ import print_function
from __future__ import unicode_literals

__version__ = '1.0pre'

from weakref import WeakValueDictionary
import functools
import httplib
import json
import urlparse
import webbrowser

import requests
import uritemplate

from restnavigator import exc, utils


DEFAULT_HEADERS = {
    'Accept': 'application/hal+json,application/json',
    'User-Agent': 'HALNavigator/{}'.format(__version__)
}

# Constants used with requests library
GET = 'GET'
POST = 'POST'
DELETE = 'DELETE'
PATCH = 'PATCH'
PUT = 'PUT'


class APICore(object):
    '''Shared data between navigators from a single api.

    This should contain all state that is generally maintained from
    one navigator to the next.
    '''

    def __init__(self,
                 root,
                 nav_class,
                 apiname=None,
                 default_curie=None,
                 session=None,
                 ):
        self.root = root
        self.nav_class = nav_class
        self.apiname = utils.namify(root) if apiname is None else apiname
        self.default_curie = default_curie
        self.session = session or requests.Session()
        self.id_map = WeakValueDictionary()

    def cache(self, link, nav):
        '''Stores a navigator in the identity map for the current
        api. Can take a link or a bare uri'''
        if link is None:
            return  # We don't cache navigators without a Link
        elif hasattr(link, 'uri'):
            self.id_map[link.uri] = nav
        else:
            self.id_map[link] = nav

    def get_cached(self, link, default=None):
        '''Retrieves a cached navigator from the id_map.

        Either a Link object or a bare uri string may be passed in.'''
        if hasattr(link, 'uri'):
            return self.id_map.get(link.uri, default)
        else:
            return self.id_map.get(link, default)

    def is_cached(self, link):
        '''Returns whether the current navigator is cached. Intended
        to be overwritten and customized by subclasses.
        '''
        if link is None:
            return False
        elif hasattr(link, 'uri'):
            return link.uri in self.id_map
        else:
            return link in self.id_map

    def authenticate(self, auth):
        '''Sets the authentication for future requests to the api'''
        self.session.auth = auth


class Link(object):
    '''Represents a HAL link. Does not store the link relation'''

    def __init__(self, uri, properties=None):
        self.uri = uri
        self.props = properties or {}

    def relative_uri(self, root):
        '''Returns the link of the current uri compared against an api root'''
        return self.uri.replace(root, '/')


class TemplatedThunk(object):
    '''A lazy representation of a navigator. Expands to a full
    navigator when template arguments are given by calling it.
    '''

    def __init__(self, link, core=None):
        self.link = link
        self._core = core

    @property
    def variables(self):
        '''Returns a set of the template variables in this templated
        link'''
        return uritemplate.variables(self.link.uri)

    def expand_uri(self, **args):
        '''Returns the template uri expanded with the current arguments'''
        args = dict([(k, v if v != 0 else '0') for k, v in args.items()])
        return uritemplate.expand(self.link.uri, args)

    def expand_link(self, **args):
        '''Expands with the given arguments and returns a new
        untemplated Link object
        '''
        props = self.link.props.copy()
        del props['templated']
        return Link(
            uri=self.expand_uri(**args),
            properties=props,
        )

    @property
    def template_uri(self):
        return self.link.uri

    def __call__(self, **args):
        '''Expands the current TemplatedThunk into a new
        navigator. Keyword args are supplied to the uri template.
        '''
        return HALNavigator(
            core=self._core,
            link=self.expand_link(**args),
        )


class Navigator(object):
    '''A factory for other navigators. Makes creating them more
    convenient
    '''

    @staticmethod
    def hal(root, apiname=None, default_curie=None, auth=None, headers=None):
        '''Create a HALNavigator'''
        root = utils.fix_scheme(root)
        halnav = HALNavigator(
            link=Link(uri=root),
            core=APICore(
                root=root,
                nav_class=HALNavigator,
                apiname=apiname,
                default_curie=default_curie,
            )
        )
        halnav.authenticate(auth)
        halnav.headers.update(DEFAULT_HEADERS)
        if headers is not None:
            halnav.headers.update(headers)
        return halnav


class HALNavigatorBase(object):
    '''Base class for navigation objects'''

    DEFAULT_CONTENT_TYPE = 'application/hal+json'

    def __new__(cls, link, core, *args, **kwargs):
        '''New decides whether we need a new instance or whether it's
        already in the id_map of the core'''
        if core.is_cached(link):
            return core.get_cached(link.uri)
        else:
            return super(HALNavigatorBase, cls).__new__(cls)

    def __init__(self, link, core,
                 response=None,
                 state=None,
                 curies=None,
                 _links=None,
                 ):
        '''Internal constructor. If you want to create a new
        HALNavigator, use the factory `Navigator.hal`
        '''
        if core.is_cached(link):
            # Don't want to overwrite a cached navigator
            return
        else:
            self.self = link
            self.response = response
            self.state = state
            self.curies = curies
            self._core = core
            self._links = _links
            core.cache(link, self)

    @property
    def uri(self):
        if self.self is not None:
            return self.self.uri

    @property
    def apiname(self):
        return self._core.apiname

    @property
    def title(self):
        if self.self is not None:
            return self.self.props.get('title')

    @property
    def profile(self):
        if self.self is not None:
            return self.self.props.get('profile')

    @property
    def type(self):
        if self.self is not None:
            return self.self.props.get('type')

    @property
    def headers(self):
        return self._core.session.headers

    @property
    def fetched(self):
        return self.response is not None

    def __repr__(self):
        relative_uri = self.self.relative_uri(self._core.root)
        objectified_uri = utils.objectify_uri(relative_uri)
        return "{cls}({name}{path})".format(
            cls=type(self).__name__, name=self.apiname, path=objectified_uri)

    def authenticate(self, auth):
        '''Authenticate with the api'''
        self._core.authenticate(auth)

    def links(self):
        '''Returns a dictionary of navigators from the current
        resource. Fetches the resource if necessary.
        '''
        if not self.fetched:
            self.fetch()
        return dict(self._links)

    @property
    def status(self):
        if self.response is not None:
            return self.response.status_code, self.response.reason

    def __eq__(self, other):
        '''Equality'''
        try:
            return self.uri == other.uri and self.apiname == other.apiname
        except Exception:
            return False

    def __ne__(self, other):
        '''Inequality'''
        return not self == other

    def __iter__(self):
        '''Part of iteration protocol'''
        yield self
        last = self
        while True:
            current = last.next()
            yield current
            last = current

    def __nonzero__(self):
        if self.response is None:
            raise exc.NoResponseError(
                'this navigator has not been fetched '
                'yet, so we cannot determine if it succeeded')
        return bool(self.response)

    def next(self):
        try:
            return self['next']
        except KeyError:
            raise StopIteration()

    def __getitem__(self, getitem_args):
        r'''Subselector for a HALNavigator'''

        def dereference(n, rels):
            '''Helper to recursively dereference'''
            n() # fetch the resource if necessary
            if len(rels) == 1:
                navigators = n._links[rels[0]]
                if isinstance(navigators, list):
                    if len(navigators) == 1:
                        return navigators[0]
                    else:
                        # copy the list
                        return list(navigators)
                else:
                    # navigators is a single item
                    return navigators
            else:
                # we still have more rels to traverse
                return dereference(n[rels[0]], rels[1:])

        rels, _, _, _ = utils.normalize_getitem_args(getitem_args)
        # If more than one rel, recursively call with 1 less rel
        n = dereference(self, rels)
        return n

    def docsfor(self, rel):
        '''Obtains the documentation for a link relation. Opens in a webbrowser
        window'''
        prefix, _rel = rel.split(':')
        if prefix in self.curies:
            doc_url = uritemplate.expand(self.curies[prefix], {'rel': _rel})
        else:
            doc_url = rel
        print('opening', doc_url)
        webbrowser.open(doc_url)

    def _make_links_from(self, body):
        '''Creates linked navigators from a HAL response body'''
        ld = utils.LinkDict(self._core.default_curie, {})
        for rel, link in body.get('_links', {}).iteritems():
            if rel not in ['self', 'curies']:
                if isinstance(link, list):
                    ld[rel] = utils.LinkList(
                        (self._navigator_or_thunk(lnk), lnk) for lnk in link)
                else:
                    ld[rel] = self._navigator_or_thunk(link)
        return ld

    def _navigator_or_thunk(self, link):
        '''Crafts a navigator or from a hal-json link dict.

        If the link is relative, the returned navigator will have a
        uri that relative to this navigator's uri.

        If the link passed in is templated, a TemplatedThunk will be
        returned instead.
        '''
        # resolve relative uris against the current uri
        uri = urlparse.urljoin(self.uri, link['href'])
        link_obj = Link(uri=uri, properties=link)
        if link.get('templated'):
            # Can expand into a real HALNavigator
            return TemplatedThunk(link_obj, core=self._core)
        else:
            return HALNavigator(link_obj, core=self._core)

    def _can_parse(self, content_type):
        '''Whether this navigator can parse the given content-type'''
        return content_type == self.DEFAULT_CONTENT_TYPE

    def _parse_content(self, text):
        '''Parses the content of a response body into the correct
        format for .state.
        '''
        try:
            return json.loads(text)
        except ValueError:
            raise exc.UnexpectedlyNotJSON(
                "The resource at {.uri} wasn't valid JSON", self)

    def _update_self_link(self, link, headers):
        '''Update the self link of this navigator'''
        self.self.props.update(link)
        # Set the self.type to the content_type of the returned document
        self.self.props['type'] = headers.get(
            'Content-Type', self.DEFAULT_CONTENT_TYPE)
        self.self.props

    def _ingest_response(self, response):
        '''Takes a response object and ingests state, links, and
        updates the self link of this navigator to correspond. This
        will only work if the response is valid JSON'''
        self.response = response
        if self._can_parse(response.headers['Content-Type']):
            hal_json = self._parse_content(response.text)
        else:
            raise exc.HALNavigatorError(
                message="Unexpected content type! Wanted {}, got {}"
                .format(self.DEFAULT_CONTENT_TYPE,
                        self.response.headers['content-type']),
                nav=self,
                status=self.response.status_code,
                response=self.response,
            )
        self._links = self._make_links_from(hal_json)
        # Set properties from new document's self link
        self._update_self_link(
            hal_json.get('_links', {}).get('self', {}),
            response.headers,
        )
        # Set curies if available
        self.curies = {curie['name']: curie['href']
                       for curie in
                       hal_json.get('_links', {}).get('curies', [])}
        # Set state by removing HAL attributes
        self.state = {k: v for k, v in hal_json.iteritems()
                      if k not in ['_links']}


class HALNavigator(HALNavigatorBase):
    '''The main navigation entity'''

    def __call__(self, raise_exc=True):
        if self.response is None:
            return self.fetch(raise_exc=raise_exc)
        else:
            return self.state.copy()

    def _create_navigator(self, response, raise_exc=True):
        '''Create the appropriate navigator from an api response'''
        method = response.request.method
        # TODO: refactor once hooks in place
        if method in (POST, PUT, PATCH, DELETE) \
           and response.status_code in (
                httplib.CREATED,
                httplib.FOUND,
                httplib.SEE_OTHER,
                httplib.NO_CONTENT) \
           and 'Location' in response.headers:
            nav = HALNavigator(
                link=Link(uri=response.headers['Location']),
                core=self._core
            )
            # We don't ingest the response because we haven't fetched
            # the newly created resource yet
        elif method in (POST, PUT, PATCH, DELETE):
            nav = OrphanHALNavigator(
                link=None,
                core=self._core,
                response=response,
                parent=self,
            )
            nav._ingest_response(response)
        elif method == GET:
            nav = self
            nav._ingest_response(response)
        else:
            assert False, "This shouldn't happen"

        return nav

    def _request(self, method, body=None, raise_exc=True, headers=None):
        '''Fetches HTTP response using the passed http method. Raises
        HALNavigatorError if response is in the 400-500 range.'''
        headers = headers or {}
        if body and 'Content-Type' not in headers:
            headers.update({'Content-Type': 'application/json'})
        response = self._core.session.request(
            method,
            self.uri,
            data=body if not isinstance(body, dict) else None,
            json=body if isinstance(body, dict) else None,
            headers=headers,
            allow_redirects=False,
        )
        nav = self._create_navigator(response, raise_exc=raise_exc)
        if raise_exc and not response:
            raise exc.HALNavigatorError(
                message=response.text,
                status=response.status_code,
                nav=nav,  # may be self
                response=response,
            )
        else:
            return nav

    def fetch(self, raise_exc=True):
        '''Performs a GET request to the uri of this navigator'''
        self._request(GET, raise_exc=raise_exc)  # ingests response
        return self.state.copy()

    def create(self, body, raise_exc=True, headers=None):
        '''Performs an HTTP POST to the server, to create a
        subordinate resource. Returns a new HALNavigator representing
        that resource.

        `body` may either be a string or a dictionary representing json
        `headers` are additional headers to send in the request
        '''
        return self._request(POST, body, raise_exc, headers)

    def delete(self, raise_exc=True, headers=None):
        '''Performs an HTTP DELETE to the server, to delete resource(s).

        `headers` are additional headers to send in the request'''

        return self._request(DELETE, None, raise_exc, headers)

    def upsert(self, body, raise_exc=True, headers=False):
        '''Performs an HTTP PUT to the server. This is an idempotent
        call that will create the resource this navigator is pointing
        to, or will update it if it already exists.

        `body` may either be a string or a dictionary representing json
        `headers` are additional headers to send in the request
        '''
        return self._request(PUT, body, raise_exc, headers)

    def patch(self, body, raise_exc=True, headers=False):
        '''Performs an HTTP PATCH to the server. This is a
        non-idempotent call that may update all or a portion of the
        resource this navigator is pointing to. The format of the
        patch body is up to implementations.

        `body` may either be a string or a dictionary representing json
        `headers` are additional headers to send in the request
        '''
        return self._request(PATCH, body, raise_exc, headers)


class OrphanHALNavigator(HALNavigatorBase):

    '''A Special navigator that is the result of a non-GET

    This navigator cannot be fetched or created, but has a special
    property called `.parent` that refers to the navigator this one
    was created from. If the result is a HAL document, it will be
    populated properly
    '''
    def __init__(self, link, core,
                 response=None,
                 state=None,
                 curies=None,
                 _links=None,
                 parent=None,
                 ):
        super(OrphanHALNavigator, self).__init__(
            link, core, response, state, curies, _links)
        self.parent = parent

    def __call__(self, *args, **kwargs):
        return self.state.copy()

    def __repr__(self):
        relative_uri = self.parent.self.relative_uri(self._core.root)
        objectified_uri = utils.objectify_uri(relative_uri)
        return "{cls}({name}{path})".format(
            cls=type(self).__name__, name=self.apiname, path=objectified_uri)

    def _can_parse(self, content_type):
        '''If something doesn't parse, we just return an empty doc'''
        return True

    def _parse_content(self, text):
        '''Try to parse as HAL, but on failure use an empty dict'''
        try:
            return super(OrphanHALNavigator, self)._parse_content(text)
        except exc.UnexpectedlyNotJSON:
            return {}

    def _update_self_link(self, link, headers):
        '''OrphanHALNavigator has no link object'''
        pass

    def _navigator_or_thunk(self, link):
        '''We need to resolve relative links against the parent uri'''
        return HALNavigatorBase._navigator_or_thunk(self.parent, link)