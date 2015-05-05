'''A library to allow navigating rest apis easy.'''

from __future__ import print_function
from __future__ import unicode_literals

__version__ = '1.0'

from weakref import WeakValueDictionary
try:
    from http import client as http_client
except ImportError:
    import httplib as http_client
import json

try:
    from urllib import parse as urlparse
except ImportError:
    import urlparse
import webbrowser

import requests
import six
import uritemplate

from restnavigator import exc, utils


DEFAULT_HEADERS = {
    'Accept': 'application/hal+json,application/json',
    'User-Agent': 'HALNavigator/{0}'.format(__version__)
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
                 id_map=None,
                 ):
        self.root = root
        self.nav_class = nav_class
        self.apiname = utils.namify(root) if apiname is None else apiname
        self.default_curie = default_curie
        self.session = session or requests.Session()
        self.id_map = id_map if id_map is not None else WeakValueDictionary()

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


class PartialNavigator(object):
    '''A lazy representation of a navigator. Expands to a full
    navigator when template arguments are given by calling it.
    '''

    def __init__(self, link, core=None):
        self.link = link
        self._core = core

    def __repr__(self):  # pragma: nocover
        relative_uri = self.link.relative_uri(self._core.root)
        objectified_uri = utils.objectify_uri(relative_uri)
        return "{cls}({name}{path})".format(
            cls=type(self).__name__,
            name=self._core.apiname,
            path=objectified_uri
        )

    @property
    def variables(self):
        '''Returns a set of the template variables in this templated
        link'''
        return uritemplate.variables(self.link.uri)

    def expand_uri(self, **kwargs):
        '''Returns the template uri expanded with the current arguments'''
        kwargs = dict([(k, v if v != 0 else '0') for k, v in kwargs.items()])
        return uritemplate.expand(self.link.uri, kwargs)

    def expand_link(self, **kwargs):
        '''Expands with the given arguments and returns a new
        untemplated Link object
        '''
        props = self.link.props.copy()
        del props['templated']
        return Link(
            uri=self.expand_uri(**kwargs),
            properties=props,
        )

    @property
    def template_uri(self):
        return self.link.uri

    def __call__(self, **kwargs):
        '''Expands the current PartialNavigator into a new
        navigator. Keyword traversal are supplied to the uri template.
        '''
        return HALNavigator(
            core=self._core,
            link=self.expand_link(**kwargs),
        )


class Navigator(object):
    '''A factory for other navigators. Makes creating them more
    convenient
    '''

    @staticmethod
    def hal(root, 
            apiname=None, 
            default_curie=None,
            auth=None, 
            headers=None, 
            session=None,
            ):
        '''Create a HALNavigator'''
        root = utils.fix_scheme(root)
        halnav = HALNavigator(
            link=Link(uri=root),
            core=APICore(
                root=root,
                nav_class=HALNavigator,
                apiname=apiname,
                default_curie=default_curie,
                session=session,
            )
        )
        if auth:
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
                 _embedded=None,
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
            self.fetched = response is not None
            self.curies = curies
            self._core = core
            self._links = _links or utils.CurieDict(core.default_curie, {})
            self._embedded = _embedded or utils.CurieDict(
                core.default_curie, {})
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
    def resolved(self):
        return self.fetched or self.state is not None

    def __repr__(self):  # pragma: nocover
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
        if not self.resolved:
            self.fetch()
        return self._links

    def embedded(self):
        '''Returns a dictionary of navigators representing embedded
        documents in the current resource. If the navigators have self
        links they can be fetched as well.
        '''
        if not self.resolved:
            self.fetch()
        return self._embedded

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
            current() # fetch if necessary
            yield current
            last = current

    def __nonzero__(self):
        '''Whether this navigator was successful.'''
        if not self.resolved:
            raise exc.NoResponseError(
                'this navigator has not been fetched '
                'yet, so we cannot determine if it succeeded')
        return bool(self.response)

    def __contains__(self, value):
        if not self.resolved:
            raise exc.NoResponseError(
                'this navigator has not been fetched '
                'yet, so we cannot determine if it contains a link '
                'relation')
        return value in self._links or value in self._embedded

    def next(self):
        try:
            return self['next']
        except exc.OffTheRailsException as otre:
            if isinstance(otre.exception, KeyError):
                raise StopIteration()
            else:
                raise

    def __getitem__(self, getitem_args):
        r'''Rel selector and traversor for navigators'''
        traversal = utils.normalize_getitem_args(getitem_args)
        intermediates = [self]
        val = self
        for i, arg in enumerate(traversal):
            try:
                if isinstance(arg, six.string_types):
                    val()  # fetch the resource if necessary
                    if val._embedded and arg in val._embedded:
                        val = val._embedded[arg]
                    else:
                        # We're hoping it's in links, otherwise we're
                        # off the tracks
                        val = val.links()[arg]
                elif isinstance(arg, tuple):
                    val = val.get_by(*arg, raise_exc=True)
                elif isinstance(arg, int) and isinstance(val, list):
                    val = val[arg]
                else:
                    raise TypeError("{0!r} doesn't accept a traversor of {1!r}"
                                    .format(val, arg))
            except Exception as e:
                raise exc.OffTheRailsException(
                    traversal, i, intermediates, e)
            intermediates.append(val)
        return val

    def docsfor(self, rel):  # pragma: nocover
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
        ld = utils.CurieDict(self._core.default_curie, {})
        for rel, link in body.get('_links', {}).items():
            if rel != 'curies':
                if isinstance(link, list):
                    ld[rel] = utils.LinkList(
                        (self._navigator_or_thunk(lnk), lnk) for lnk in link)
                else:
                    ld[rel] = self._navigator_or_thunk(link)
        return ld

    def _make_embedded_from(self, doc):
        '''Creates embedded navigators from a HAL response doc'''
        ld = utils.CurieDict(self._core.default_curie, {})
        for rel, doc in doc.get('_embedded', {}).items():
            if isinstance(doc, list):
                ld[rel] = [self._recursively_embed(d) for d in doc]
            else:
                ld[rel] = self._recursively_embed(doc)
        return ld

    def _recursively_embed(self, doc, update_state=True):
        '''Crafts a navigator from a hal-json embedded document'''
        self_link = None
        self_uri = utils.getpath(doc, '_links.self.href')
        if self_uri is not None:
            uri = urlparse.urljoin(self.uri, self_uri)
            self_link = Link(
                uri=uri,
                properties=utils.getpath(doc, '_links.self')
            )
        curies = utils.getpath(doc, '_links.curies')
        state = utils.getstate(doc)
        if self_link is None:
            nav = OrphanHALNavigator(
                link=None,
                response=None,
                parent=self,
                core=self._core,
                curies=curies,
                state=state,
            )
        else:
            nav = HALNavigator(
                link=self_link,
                response=None,
                core=self._core,
                curies=curies,
                state=state,
            )
        if update_state:
            nav.state = state

        links = self._make_links_from(doc)
        if links is not None:
            nav._links = links
        embedded = self._make_embedded_from(doc)
        if embedded is not None:
            nav._embedded = embedded
        return nav


    def _navigator_or_thunk(self, link):
        '''Crafts a navigator or from a hal-json link dict.

        If the link is relative, the returned navigator will have a
        uri that relative to this navigator's uri.

        If the link passed in is templated, a PartialNavigator will be
        returned instead.
        '''
        # resolve relative uris against the current uri
        uri = urlparse.urljoin(self.uri, link['href'])
        link_obj = Link(uri=uri, properties=link)
        if link.get('templated'):
            # Can expand into a real HALNavigator
            return PartialNavigator(link_obj, core=self._core)
        else:
            return HALNavigator(link_obj, core=self._core)

    def _can_parse(self, content_type):
        '''Whether this navigator can parse the given content-type.
        Checks that the content_type matches one of the types specified
        in the 'Accept' header of the request, if supplied.
        If not supplied, matches against the default'''
        content_type, content_subtype, content_param = utils.parse_media_type(content_type)
        for accepted in self.headers.get('Accept', self.DEFAULT_CONTENT_TYPE).split(','):
            type, subtype, param = utils.parse_media_type(accepted)
            # if either accepted_type or content_type do not
            # contain a parameter section, then it will be
            # optimistically ignored
            matched = (type == content_type) \
                      and (subtype == content_subtype) \
                      and (param == content_param or not (param and content_param))
            if matched:
                return True
        return False

    def _parse_content(self, text):
        '''Parses the content of a response doc into the correct
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
        '''Takes a response object and ingests state, links, embedded
        documents and updates the self link of this navigator to
        correspond. This will only work if the response is valid
        JSON
        '''
        self.response = response
        if self._can_parse(response.headers['Content-Type']):
            hal_json = self._parse_content(response.text)
        else:
            raise exc.HALNavigatorError(
                message="Unexpected content type! Wanted {0}, got {1}"
                .format(self.headers.get('Accept', self.DEFAULT_CONTENT_TYPE),
                        self.response.headers['content-type']),
                nav=self,
                status=self.response.status_code,
                response=self.response,
            )
        self._links = self._make_links_from(hal_json)
        self._embedded = self._make_embedded_from(hal_json)
        # Set properties from new document's self link
        self._update_self_link(
            hal_json.get('_links', {}).get('self', {}),
            response.headers,
        )
        # Set curies if available
        self.curies = dict(
            (curie['name'], curie['href'])
            for curie in
            hal_json.get('_links', {}).get('curies', []))
        # Set state by removing HAL attributes
        self.state = utils.getstate(hal_json)


class HALNavigator(HALNavigatorBase):
    '''The main navigation entity'''

    def __call__(self, raise_exc=True):
        if not self.resolved:
            return self.fetch(raise_exc=raise_exc)
        else:
            return self.state.copy()

    def _create_navigator(self, response, raise_exc=True):
        '''Create the appropriate navigator from an api response'''
        method = response.request.method
        # TODO: refactor once hooks in place
        if method in (POST, PUT, PATCH, DELETE) \
           and response.status_code in (
                http_client.CREATED,
                http_client.FOUND,
                http_client.SEE_OTHER,
                http_client.NO_CONTENT) \
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
        else: # pragma: nocover
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
        self.fetched = True
        return self.state.copy()

    def create(self, body=None, raise_exc=True, headers=None):
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

    def __repr__(self):  # pragma: nocover
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
