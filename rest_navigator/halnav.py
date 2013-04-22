'''A library to allow navigating rest apis easy.'''

from __future__ import unicode_literals
from __future__ import print_function

import copy
from weakref import WeakValueDictionary

import requests
import uritemplate

import exc
import utils


class HALNavigator(object):
    '''The main navigation entity'''

    def __init__(self, root, name=None):
        self.root = utils.fix_scheme(root)
        self.name = root if name is None else name
        self.url = self.root
        self.profile = None
        self.title = None
        self.type = 'application/hal+json'
        self.response = None
        self.state = None
        self.templated = False

        self._links = None
        #This is the identity map shared by all descendents of this HALNavigator
        self._id_map = WeakValueDictionary({self.root: self})

    def __repr__(self):
        return "HALNavigator('{.name}')".format(self)

    @property
    @utils.autofetch
    def links(self):
        r'''Returns links from the current resource'''
        return self._links

    def GET(self):
        r'''Handles GET requests for a resource'''
        if self.templated:
            raise exc.AmbiguousNavigationError(
                '''This is a templated Navigator. You must provide values for the template
                parameters before fetching the resource or else explicitly null
                them out with the syntax: N[:]''')
        self.response = requests.get(self.url)
        body = self.response.json()
        self._links = {rel: self._copy(url=link['href'],
                                       rel=rel,
                                       title=link.get('title'),
                                       type=link.get('type'),
                                       profile=link.get('profile'),
                                       templated=link.get('templated'),
                                   )
                       for rel, link in body.get('_links', {}).iteritems()
                       if rel != 'self'}
        self.title = body.get('_links', {}).get('self', {}).get('title', self.title)
        self.state = {k:v for k,v in self.response.json().iteritems()
                      if k not in ('_links', '_embedded')}
        self.state.pop('_links', None)
        self.state.pop('_embedded', None)

    def _copy(self, **kwargs):
        '''Creates a shallow copy of the HALNavigator that extra attributes can be set on.
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

    def __eq__(self, other):
        return self.url == other.url and self.name == other.name

    @utils.autofetch
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

    def expand(self, **kwargs):
        '''Expand template args in a templated Navigator. Returns a non-templated
        HALNavigator'''
        if not self.templated:
            raise TypeError("This Navigator isn't templated! You can't expand it.")
        for k,v in kwargs.iteritems():
            if v == 0:
                kwargs[k] = '0'  # uritemplate expands 0's to empty string
        return self._copy(url=uritemplate.expand(self.url, kwargs))


    def __getitem__(self, getitem_args):
        r'''Subselector for a HALNavigator'''
        args, kwargs = utils.normalize_getitem_args(getitem_args)
        if None in kwargs and kwargs[None] == None:
            slug = True
            kwargs.pop(None)
        else:
            slug = False
        if Ellipsis in args:
            ellipsis = True
            args.remove(Ellipsis)
        else:
            ellipsis = False
        if not self.templated and not args and kwargs:
            raise ValueError('This Navigator is not templated, but you are '
                             'nevertheless trying to expand it.')
        if len(args) == 0 and 
            # only one arg, and it's a slice
            return self.expand(**utils.slice_process(args))
        else:
            # string arg, which should be a rel-type
            if self.response is None:
                self.GET()
            return self._links[args]
        if isinstance(args, tuple)
            if isinstance(args[0], slice):
                return self.expand(**kwargs)
            else:
                if self.response is None:
                    self.GET()
                expanded_url = 
                return self._copy()
