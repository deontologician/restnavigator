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
    

class Navigator(object):
    '''The main navigation entity'''
    
    def __init__(self, root, name=None):
        self.root = root
        self.name = root if name is None else name
        self.url = root
        self.profile = None
        self.title = None
        self.type = 'application/hal+json'
        self.response = None

        self._links = None        

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
        self._links = {rel: self._copy(url=link['href'],
                                       rel=rel,
                                       title=link.get('title'),
                                       type=link.get('type'),
                                       profile=link.get('profile')
                                   )
                       for rel, link in self.response.json()['_links'].iteritems()}

    def _copy(self, **kwargs):
        '''Creates a shallow copy of the Navigator that extra attributes can be set on'''
        cp = copy.copy(self)
        cp._links = None
        cp.response = None
        for attr, val in kwargs.iteritems():
            if val is not None:
                setattr(cp, attr, val)
        return cp

    @autofetch
    def __getitem__(self, key):
        r'''Subselector for a Navigator'''
        return self._links[key]

    def __eq__(self, other):
        return self.url == other.url and self.name == other.name
