# -*- coding: utf-8 -*-
from __future__ import print_function

import urlparse
import re
import collections
import itertools
import urllib

import unidecode

from restnavigator import exc


def fix_scheme(url):
    '''Prepends the http:// scheme if necessary to a url. Fails if a scheme
    other than http is used'''
    splitted = url.split('://')
    if len(splitted) == 2:
        if splitted[0] == 'http':
            return url
        else:
            raise exc.WileECoyoteException(
                'Bad scheme! Got: {}, expected http'.format(splitted[0]))
    elif len(splitted) == 1:
        return 'http://' + url
    else:
        raise exc.ZachMorrisException('Too many schemes!')


def slice_process(slc):
    '''Returns dictionaries for different slice syntaxes.'''
    if slc.step is None:
        if slc.start is not None and slc.stop is not None:
            return {slc.start: slc.stop}
        if slc.start is not None and slc.stop is None:
            return {slc.start: ''}
        if slc.start is None and slc.stop is None:
            return {None:None}  # a sentinel indicating 'No further expanding please'
        # maybe more slice types later if there is a good reason
    raise ValueError('Unsupported slice syntax')


def normalize_getitem_args(args):
    '''Turns the arguments to __getitem__ magic methods into a uniform list of
    dictionaries and strings (and Ellipsis)
    '''
    if not isinstance(args, tuple):
        args = args,
    qargs = {}
    rels = []
    ellipsis = False
    slug = False
    for arg in args:
        if isinstance(arg, basestring):
            rels.append(arg)
        elif isinstance(arg, slice):
            slc = slice_process(arg)
            if slc == {None:None}:
                slug = True
            else:
                qargs.update(slc)
        elif isinstance(arg, type(Ellipsis)):
            ellipsis = True
        else:
            raise TypeError(
                'Brackets cannot contain objects of type {.__name__}'
                .format(type(arg)))
    return rels, qargs, slug, ellipsis


def namify(root_uri):
    '''Turns a root uri into a less noisy representation that will probably
    make sense in most circumstances. Used by Navigator's __repr__, but can be
    overridden if the Navigator is created with a 'name' parameter.'''

    root_uri = unidecode.unidecode(urllib.unquote(root_uri).decode('utf-8'))

    generic_domains = set(['herokuapp', 'appspot'])
    urlp = urlparse.urlparse(fix_scheme(root_uri))
    formatargs = collections.defaultdict(list)

    domain, tld = urlp.netloc.lower().rsplit('.', 1)
    if '.' in domain:
        subdomain, domain = domain.rsplit('.', 1)
    else:
        subdomain = ''

    if subdomain != 'www':
        formatargs['subdomain'] = subdomain.split('.')
    if domain not in generic_domains:
        formatargs['domain'].append(domain)
    if len(tld) == 2:
        formatargs['tld'].append(tld.upper())
    elif tld != 'com':
        formatargs['tld'].append(tld)

    formatargs['path'].extend(p for p in urlp.path.lower().split('/') if p)
    formatargs['qargs'].extend(r for q in urlp.query.split(',')
                               for r in q.split('=') if q and r)

    def capify(s):
        '''Capitalizes the first letter of a string, but doesn't downcase the
        rest like .title()'''
        return s if not s else s[0].upper() + s[1:]

    def piece_filter(piece):
        if piece.lower() == 'api':
            formatargs['api'] = True
            return ''
        elif re.match(r'v[\d.]+', piece):
            formatargs['version'].extend(['.', piece])
            return ''
        elif 'api' in piece:
            return piece.replace('api', 'API')
        else:
            return piece

    chain = itertools.chain
    imap = itertools.imap
    pieces = imap(capify, imap(piece_filter, chain(
        formatargs['subdomain'],
        formatargs['domain'],
        formatargs['tld'],
        formatargs['path'],
        formatargs['qargs'],
    )))
    return '{pieces}{api}{vrsn}'.format(pieces=''.join(pieces),
                                        api='API' if formatargs['api'] else '',
                                        vrsn=''.join(formatargs['version']),
                                        )


class LinkList(list):
    '''A list subclass that offers different ways of grabbing the values based
    on various metadata stored for each entry in the dictionary.

    Note: Removing items from this list isn't really the point, so no attempt
    has been made to make this convenient. Deleting items will not remove them
    from the list's metadata.'''

    def __init__(self, items=None):
        super(LinkList, self).__init__()
        self._meta = {}
        items = items or []
        for obj, properties in items:
            self.append_with(obj, **properties)

    # Values coming in on properties might be unhashable, so we serialize them
    serialize = staticmethod(unicode)  # json comes in as unicode

    def append_with(self, obj, **properties):
        '''Add an item to the dictionary with the given metadata properties'''
        for prop, val in properties.iteritems():
            val = self.serialize(val)
            self._meta.setdefault(prop, {}).setdefault(val, []).append(obj)
        self.append(obj)

    def get_by(self, prop, val):
        '''Retrieve an item from the dictionary with the given metadata
        properties. If there is no such item, None will be returned, if there
        are multiple such items, the first will be returned.'''
        try:
            val = self.serialize(val)
            return self._meta[prop][val][0]
        except (KeyError, IndexError):
            return None

    def getall_by(self, prop, val):
        '''Retrieves all items from the dictionary with the given metadata'''
        try:
            val = self.serialize(val)
            return self._meta[prop][val][:]  # return a copy of the list
        except KeyError:
            return []

    def named(self, name):
        '''Returns .get_by('name', name)'''
        name = self.serialize(name)
        return self.get_by('name', name)
