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


def autofetch(fn):
    '''A decorator used by Navigators that fetches the resource if necessary
    prior to calling the function '''

    @functools.wraps(fn)
    def wrapped(self, *args, **qargs):
        if self.self is not None and self.response is None:
            self.fetch(raise_exc=qargs.get('raise_exc', False))
        return fn(self, *args, **qargs)

    return wrapped

def get_state(hal_body):
    '''Removes HAL special properties from a HAL+JSON response'''
    return {k: v for k, v in hal_body.iteritems()
            if k not in ['_links']} 

class APICore(object):
    '''Shared data between Navigators from a single api.

    This should contain all state that is generally maintained from
    one Navigator to the next.
    '''

    def __init__(self,
                 root,
                 nav_class,
                 apiname=None,
                 default_curie=None,
                 session=None,
                 ):
        self.root = utils.fix_scheme(root)
        self.nav_class = nav_class
        self.apiname = utils.namify(root) if apiname is None else apiname
        self.default_curie = default_curie
        self.session = session or requests.Session()
        self.id_map = WeakValueDictionary()

    def cache(self, link, nav):
        '''Stores a Navigator in the identity map for the current
        api. Can take a link or a bare uri'''
        if link is None:
            return  # We don't cache Navigators without a Link
        elif hasattr(link, 'uri'):
            self.id_map[link.uri] = nav
        else:
            self.id_map[link] = nav

    def get_cached(self, link, default=None):
        '''Retrieves a cached Navigator from the id_map.

        Either a Link object or a bare uri string may be passed in.'''
        if hasattr(link, 'uri'):
            return self.id_map.get(link.uri, default)
        else:
            return self.id_map.get(link, default)

    def is_cached(self, link):
        '''Returns whether the current Navigator is cached. Intended
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

    def create_navigator(self, link):
        '''Rehydrates a Navigator with this core given a link'''
        return self.nav_class(link=link, core=self)


class Link(object):
    '''Represents an untemplated link'''

    def __init__(self, uri, properties=None):
        self.uri = uri
        self.props = properties or {}

    def relative_uri(self, root):
        '''Returns the link of the current uri compared against an api root'''
        return self.uri.replace(root, '/')


class TemplatedLink(Link):
    '''Represents a templated link'''

    def __init__(self, uri, properties=None, args=None, core=None):
        super(TemplatedLink, self).__init__(uri, properties)
        self.args = args or {}
        self._core = core

    @property
    def variables(self):
        '''Returns a set of the template variables in this templated
        link'''
        return uritemplate.variables(self.uri)

    def add_args(self, **args):
        '''Returns a new TemplatedLink with additional arguments baked
        in. Does not modify the current TemplatedLink.
        '''
        argcopy = self.args.copy()
        argcopy.update(args)
        return TemplatedLink(
            uri=self.uri,
            properties=self.props,
            args=argcopy
        )

    def expand_uri(self, **args):
        '''Returns the template uri expanded with the current arguments'''
        expandargs = dict([(k, v if v != 0 else '0')
                           for k, v in self.args.items() + args.items()])
        return uritemplate.expand(self.template_uri, expandargs)

    def expand_link(self, **args):
        '''Expands this TemplatedLink with the given arguments and
        returns a new Link (untemplated).
        '''
        props = self.props.copy()
        del props['templated']
        return Link(
            uri=self.expand_uri(**args),
            properties=props,
        )

    def navigator(self, **args):
        '''Expands the current TemplatedLink into a new Navigator from
        the APICore passed in. Keyword args are supplied to the uri
        template.
        '''
        return self._core.create_navigator(self.expand_link(**args))

    def __getitem__(self, getitem_args):
        _, qargs, slug, ellipsis = utils.normalize_getitem_args(
            getitem_args)
        if slug and ellipsis:
            raise SyntaxError("':' and '...' syntax cannot be combined!")
        elif slug or qargs:
            return self.navigator(**qargs)
        elif ellipsis:
            return self.add_args(**qargs)
        else:
            raise Exception('Impossible!', qargs, slug, ellipsis)

class Navigator(object):
    '''A factory for other Navigators. Makes creating them more
    convenient
    '''

    @staticmethod
    def hal(root, apiname=None, default_curie=None, auth=None, headers=None):
        '''Create a HALNavigator'''
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
            # Don't want to overwrite a cached Navigator
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
        return self.self.uri

    @property
    def apiname(self):
        return self._core.apiname

    @property
    def title(self):
        return self.self.props.get('title')

    @property
    def profile(self):
        return self.self.props.get('profile')

    @property
    def type(self):
        return self.self.props.get('type')

    @property
    def headers(self):
        return self._core.session.headers

    def __repr__(self):
        relative_uri = self.self.relative_uri(self._core.root)
        objectified_uri = utils.objectify_uri(relative_uri)
        return "{cls}({name}{path})".format(
            cls=type(self).__name__, name=self.apiname, path=objectified_uri)

    def authenticate(self, auth):
        '''Authenticate with the api'''
        self._core.authenticate(auth)

    @property
    @autofetch
    def links(self):
        '''Returns a dictionary of Navigators from the current resource'''
        return dict(self._links)

    @property
    @autofetch
    def status(self):
        return (self.response.status_code, self.response.reason)

    def _make_links_from(self, body):
        '''Creates linked navigators from a HAL response body'''

        def make_nav(link):
            '''Crafts the Navigators for each link'''
            if isinstance(link, list):
                return utils.LinkList((make_nav(lnk), lnk) for lnk in link)
            uri = urlparse.urljoin(self.uri, link['href'])
            if link.get('templated'):
                return TemplatedLink(uri=uri, properties=link)
            else:
                return HALNavigator(
                    link=Link(uri=uri, properties=link),
                    core=self._core,
                )

        return utils.LinkDict(
            self._core.default_curie,
            {rel: make_nav(links)
             for rel, links in body.get('_links', {}).iteritems()
             if rel not in ['self', 'curies']})

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

    @autofetch
    def __nonzero__(self):
        # we override normal exception throwing since the user seems interested
        # in the boolean value
        return bool(self.response)

    def next(self):
        try:
            return self['next']
        except KeyError:
            raise StopIteration()

    def __getitem__(self, getitem_args):
        r'''Subselector for a HALNavigator'''

        @autofetch
        def dereference(n, rels):
            '''Helper to recursively dereference'''
            if len(rels) == 1:
                ret = n._links[rels[0]]
                if isinstance(ret, list):
                    if len(ret) == 1:
                        return ret[0]
                    else:
                        return [r._copy() if r.templated else r for r in ret]
                else:
                    return ret._copy() if ret.templated else ret
            else:
                return dereference(n[rels[0]], rels[1:])

        rels, qargs, slug, ellipsis = utils.normalize_getitem_args(
            getitem_args)
        if slug and ellipsis:
            raise SyntaxError("':' and '...' syntax cannot be combined!")
        if rels:
            n = dereference(self, rels)
        else:
            n = self
        if qargs or slug:
            n = n.expand(_keep_templated=ellipsis, **qargs)
        return n

    @autofetch
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


class HALNavigator(HALNavigatorBase):
    '''The main navigation entity'''

    def fetch(self, raise_exc=True):
        '''Like __call__, but doesn't cache, always makes the request'''
        self.response = self._core.session.get(self.uri)
        try:
            body = json.loads(self.response.text)
        except ValueError:
            if raise_exc:
                raise UnexpectedlyNotJSON(
                    "The resource at {.uri} wasn't valid JSON", self.response)
            else:
                return
        self._links = self._make_links_from(body)
        # Set properties from new document's self link
        self.self.props.update(
            body.get('_links', {}).get('self', {}))
        # Set the self.type to the content_type of the returned document
        self.self.props['type'] = self.response.headers.get(
            'Content-Type', HALNavigator.DEFAULT_CONTENT_TYPE)
        # Set curies if available
        self.curies = {curie['name']: curie['href']
                       for curie in body.get('_links', {}).get('curies', [])}
        self.state = get_state(body)
        if raise_exc and not self.response:
            raise HALNavigatorError(self.response.text,
                                    status=self.status,
                                    nav=self,
                                    response=self.response,
            )
        return self.state.copy()

    def __call__(self, raise_exc=True):
        if self.response is None:
            return self.fetch(raise_exc=raise_exc)
        else:
            return self.state.copy()

    def _get_http_response(self,
                            http_method_fn,
                            body,
                            raise_exc=True,
                            content_type='application/json',
                            json_cls=None,
                            headers=None,
    ):
        '''Fetches HTTP response using http method (POST or DELETE of
        requests.Session) Raises HALNavigatorError if response is not
        positive
        '''
        if isinstance(body, dict):
            body = json.dumps(body, cls=json_cls, separators=(',', ':'))
        headers = {} if headers is None else headers
        headers['Content-Type'] = content_type
        response = http_method_fn(
            self.uri, data=body, headers=headers, allow_redirects=False)

        if raise_exc and not response:
            raise HALNavigatorError(
                message=response.text,
                status=response.status_code,
                nav=self,
                response=response,
            )
        return response

    def _create_navigator_or_orphan_resource(self, response):
        if response.status_code in (httplib.CREATED, # Applicable for POST
                                    httplib.FOUND,
                                    httplib.SEE_OTHER,
                                    httplib.NO_CONTENT,
        ) and 'Location' in response.headers:
            return self._copy(uri=response.headers['Location'])
        elif response.status_code == httplib.OK:
            return OrphanResource(parent=self, response=response)
        else:
        # Expected hits:
        # CREATED or Redirection without Locaiton,
        # NO_CONTENT = 204
        # ACCEPTED = 202 and
        # 4xx, 5xx errors.

        # If something else, then requires rework
            return self.status

    def create(self,
             body,
             raise_exc=True,
             content_type='application/json',
             json_cls=None,
             headers=None,
             ):
        '''Performs an HTTP POST to the server, to create a subordinate
        resource. Returns a new HALNavigator representing that resource.

        `body` may either be a string or a dictionary which will be serialized
            as json
        `content_type` may be modified if necessary
        `json_cls` is a JSONEncoder to use rather than the standard
        `headers` are additional headers to send in the request'''
        response = self._get_http_response(
            self.session.post,
            body,
            raise_exc,
            content_type,
            json_cls,
            headers,
        )

        return self._create_navigator_or_orphan_resource(response)

    def delete(self,
               raise_exc=True,
               headers=None,
               ):
        '''Performs an HTTP DELETE to the server, to delete resource(s).
        `body` may either be a string or a dictionary which will be serialized
            as json
        `content_type` may be modified if necessary
        `json_cls` is a JSONEncoder to use rather than the standard
        `headers` are additional headers to send in the request'''

        response = self._get_http_response(
            self.session.delete,
            body=None,
            raise_exc=raise_exc,
            content_type=None,
            json_cls=None,
            headers=None,
        )
        return self._create_navigator_or_orphan_resource(response)


class OrphanHALNavigator(HALNavigator):
    '''A Special Navigator that is the result of a non-GET

    This Navigator cannot be fetched or created, but has a special
    property called `.parent` that refers to the Navigator this one
    was created from. If the result is a HAL document,
    this object's `.links` property will be populated.

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


class HALNavigatorError(Exception):
    '''Raised when a response is an error

    Has all of the attributes of a normal HALNavigator. The error body can be
    returned by examining response.body '''

    def __init__(self, message, nav=None, status=None, response=None):
        self.nav = nav
        self.response = response
        self.message = message
        self.status = status
        super(HALNavigatorError, self).__init__(message)


class UnexpectedlyNotJSON(TypeError):
    '''Raised when a non-json parseable resource is gotten'''

    def __init__(self, msg, response):
        self.msg = msg
        self.response = response

    def __repr__(self):  # pragma: nocover
        return '{.msg}:\n\n\n{.response}'.format(self)
