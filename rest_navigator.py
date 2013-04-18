'''A library to allow navigating rest apis easy.'''

from __future__ import unicode_literals
from __future__ import print_function

import copy
from functools import wraps

import requests


def autofetch(fn):
    @wraps(fn)
    def wrapped(self, *args, **kwargs):
        if self.response is None:
            self.GET()
        return fn(self, *args, **kwargs)
    return wrapped


class WileECoyoteException(ValueError):
    '''Raised when a url has a bad scheme'''
    pass


class ZachMorrisException(ValueError):
    '''Raised when a url has too many schemes'''
    pass


def fix_scheme(url):
    '''Appends the http:// scheme if necessary to a url. Fails if a scheme
    other than http is used'''
    splitted = url.split('://')
    if len(splitted) == 2:
        if splitted[0] == 'http':
            return url
        else:
            raise WileECoyoteException(
                'Bad scheme! Got: {}, expected http'.format(splitted[0]))
    elif len(splitted) == 1:
        return 'http://' + url
    else:
        raise ZachMorrisException('Too many schemes!')


class Navigator(object):
    '''The main navigation entity'''

    def __init__(self, root, name=None):
        self.root = fix_scheme(root)
        self.name = root if name is None else name
        self.url = self.root
        self.profile = None
        self.title = None
        self.type = 'application/hal+json'
        self.response = None
        self.state = None

        self._links = None
        #This is the identity map shared by all descendents of this Navigator
        self._id_map = {self.root: self}

    def __repr__(self):
        return "Navigator('{.name}')".format(self)

    @property
    @autofetch
    def links(self):
        r'''Returns links from the current resource'''
        return self._links

    def GET(self):
        r'''Handles GET requests for a resource'''
        self.response = requests.get(self.url)
        body = self.response.json()
        self._links = {rel: self._copy(url=link['href'],
                                       rel=rel,
                                       title=link.get('title'),
                                       type=link.get('type'),
                                       profile=link.get('profile')
                                   )
                       for rel, link in body.get('_links', {}).iteritems()
                       if rel != 'self'}
        self.title = body.get('_links', {}).get('self', {}).get('title', self.title)
        self.state = {k:v for k,v in self.response.json().iteritems()
                      if k not in ('_links', '_embedded')}
        self.state.pop('_links', None)
        self.state.pop('_embedded', None)

    def _copy(self, **kwargs):
        '''Creates a shallow copy of the Navigator that extra attributes can be set on.
        If the object is already in the identity map, that object is returned instead
        '''
        if 'url' in kwargs and kwargs['url'] in self._id_map:
            return self._id_map[kwargs['url']]
        cp = copy.copy(self)
        cp._links = None
        cp.response = None
        for attr, val in kwargs.iteritems():
            if attr == 'url':
                self._id_map[val] = cp
            if val is not None:
                setattr(cp, attr, val)
        return cp

    @autofetch
    def __getitem__(self, key):
        r'''Subselector for a Navigator'''
        return self._links[key]

    def __eq__(self, other):
        return self.url == other.url and self.name == other.name

    @autofetch
    def __call__(self):
        return self.state.copy()

    def __iter__(self):
        '''Part of iteration protocol'''
        last = self
        while True:
            current = last.next()
            yield current
            last = current

    def next(self):
        try:
            return self['next']
        except KeyError:
            raise StopIteration()
