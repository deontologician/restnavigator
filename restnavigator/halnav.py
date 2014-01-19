'''A library to allow navigating rest apis easy.'''

from __future__ import print_function

__version__ = '0.2'

import copy
from weakref import WeakValueDictionary
import functools
import httplib
import re
import json
import urlparse
import webbrowser
import urllib

import requests
import unidecode
import uritemplate

from restnavigator import exc, utils


def autofetch(fn):
    '''A decorator used by Navigators that fetches the resource if necessary
    prior to calling the function '''

    @functools.wraps(fn)
    def wrapped(self, *args, **qargs):
        if self.response is None:
            self._GET()
        return fn(self, *args, **qargs)
    return wrapped


def default_headers():
    '''Default headers for HALNavigator'''
    return {'Accept': 'application/hal+json,application/json',
            'User-Agent': 'HALNavigator/{}'.format(__version__)}


class HALNavigator(object):
    '''The main navigation entity'''

    def __init__(
            self, root, apiname=None, auth=None, headers=None, session=None):
        self.root = utils.fix_scheme(root)
        self.apiname = utils.namify(root) if apiname is None else apiname
        self.uri = self.root
        self.profile = None
        self.title = None
        self.type = 'application/hal+json'
        self.curies = None
        self.session = session or requests.Session()
        self.session.auth = auth
        self.session.headers.update(default_headers())
        if headers:
            self.session.headers.update(headers)
        self.response = None
        self.state = None
        self.template_uri = None
        self.template_args = None
        self.parameters = None
        self.templated = False
        self._links = None
        # This is the identity map shared by all descendents of this
        # HALNavigator
        self._id_map = WeakValueDictionary({self.root: self})

    def __repr__(self):
        def path_clean(chunk):
            if not chunk:
                return chunk
            if re.match(r'\d+$', chunk):
                return '[{}]'.format(chunk)
            else:
                return '.' + chunk
        byte_arr = self.relative_uri.encode('utf-8')
        unquoted = urllib.unquote(byte_arr).decode('utf-8')
        nice_uri = unidecode.unidecode(unquoted)
        path = ''.join(path_clean(c) for c in nice_uri.split('/'))
        return "HALNavigator({name}{path})".format(
                name=self.apiname, path=path)

    def authenticate(self, auth):
        '''Allows setting authentication for future requests to the api'''
        self.session.auth = auth

    @property
    def relative_uri(self):
        '''Returns the link of the current uri compared against the api root.

        This is a good candidate for overriding in a subclass if the api you
        are interacting with uses an unconventional uri layout.'''
        if self.uri is None:
            return self.template_uri.replace(self.root, '/')
        else:
            return self.uri.replace(self.root, '/')

    @property
    @autofetch
    def links(self):
        r'''Returns dictionary of navigators from the current resource.'''
        return dict(self._links)

    @property
    def status(self):
        if self.response is not None:
            return (self.response.status_code, self.response.reason)

    def _GET(self, raise_exc=True):
        r'''Handles GET requests for a resource'''
        if self.templated:
            raise exc.AmbiguousNavigationError(
                'This is a templated Navigator. You must provide values for '
                'the template parameters before fetching the resource or else '
                'explicitly null them out with the syntax: N[:]')
        self.response = self.session.get(self.uri)
        try:
            body = self.response.json()
        except ValueError as e:
            if raise_exc:
                raise UnexpectedlyNotJSON(
                    "The resource at {.uri} wasn't valid JSON", self.response)
            else:
                return

        def make_nav(link):
            '''Crafts the Navigators for each link'''
            if isinstance(link, list):
                return utils.LinkList((make_nav(l), l) for l in link)
            templated = link.get('templated', False)
            if not templated:
                uri = urlparse.urljoin(self.uri, link['href'])
                template_uri = None
            else:
                uri = None
                template_uri = urlparse.urljoin(self.uri, link['href'])
            cp = self._copy(uri=uri,
                            template_uri=template_uri,
                            templated=templated,
                            title=link.get('title'),
                            type=link.get('type'),
                            profile=link.get('profile'),
                            )
            if templated:
                cp.uri = None
                cp.parameters = uritemplate.variables(cp.template_uri)
            else:
                cp.template_uri = None
            return cp
        self._links = {}
        for rel, links in body.get('_links', {}).iteritems():
            if rel not in ('self', 'curies'):
                self._links[rel] = make_nav(links)
        self.title = body.get('_links', {}).get('self', {}).get(
            'title', self.title)
        if 'curies' in body.get('_links', {}):
            curies = body['_links']['curies']
            self.curies = {curie['name']: curie['href'] for curie in curies}
        self.state = {k: v for k, v in self.response.json().iteritems()
                      if k not in ('_links', '_embedded')}
        self.state.pop('_links', None)
        self.state.pop('_embedded', None)
        if raise_exc and not self.response:
            raise HALNavigatorError(self.response.text,
                                    status=self.status,
                                    nav=self,
                                    response=self.response,
                                    )

    def _copy(self, **kwargs):
        '''Creates a shallow copy of the HALNavigator that extra attributes can
        be set on.

        If the object is already in the identity map, that object is returned
        instead.
        If the object is templated, it doesn't go into the id_map
        '''
        if 'uri' in kwargs and kwargs['uri'] in self._id_map:
            return self._id_map[kwargs['uri']]
        cp = copy.copy(self)
        cp._links = None
        cp.response = None
        cp.state = None
        cp.fetched = False
        for attr, val in kwargs.iteritems():
            if val is not None:
                setattr(cp, attr, val)
        if not cp.templated:
            self._id_map[cp.uri] = cp
        return cp

    def __eq__(self, other):
        try:
            return self.uri == other.uri and self.apiname == other.apiname
        except Exception:
            return False

    def __ne__(self, other):
        return not self == other

    def __call__(self, raise_exc=True):
        if self.response is None:
            self._GET(raise_exc=raise_exc)
        return self.state.copy()

    def fetch(self, raise_exc=True):
        '''Like __call__, but doesn't cache, always makes the request'''
        self._GET(raise_exc=raise_exc)
        return self.state.copy()

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
        if isinstance(body, dict):
            body = json.dumps(body, cls=json_cls, separators=(',', ':'))
        headers = {} if headers is None else headers
        headers['Content-Type'] = content_type
        response = self.session.post(
            self.uri, data=body, headers=headers, allow_redirects=False)
        if raise_exc and not response:
            raise HALNavigatorError(
                message=response.text,
                status=response.status_code,
                nav=self,
                response=response,
            )
        if response.status_code in (httplib.CREATED,
                                    httplib.ACCEPTED,
                                    httplib.FOUND,
                                    httplib.SEE_OTHER,
                                    ) and 'Location' in response.headers:
            return self._copy(uri=response.headers['Location'])
        else:
            return (response.status_code, response)

    def __iter__(self):
        '''Part of iteration protocol'''
        last = self
        while True:
            current = last.next()
            yield current
            last = current

    def __nonzero__(self):
        # we override normal exception throwing since the user seems interested
        # in the boolean value
        if self.response is None:
            self._GET(raise_exc=False)
        return bool(self.response)

    def next(self):
        try:
            return self['next']
        except KeyError:
            raise StopIteration()

    def expand(self, _keep_templated=False, **kwargs):
        '''Expand template args in a templated Navigator.

        if :_keep_templated: is True, the resulting Navigator can be further
        expanded. A Navigator created this way is not part of the id map.
        '''

        if not self.templated:
            raise TypeError(
                "This Navigator isn't templated! You can't expand it.")

        for k, v in kwargs.iteritems():
            if v == 0:
                kwargs[k] = '0'  # uritemplate expands 0's to empty string

        if self.template_args is not None:
            kwargs.update(self.template_args)
        cp = self._copy(uri=uritemplate.expand(self.template_uri, kwargs),
                        templated=_keep_templated,
                        )
        if not _keep_templated:
            cp.template_uri = None
            cp.template_args = None
        else:
            cp.template_args = kwargs

        return cp

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
