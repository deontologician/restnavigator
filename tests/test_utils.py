# -*- coding: utf-8 -*-
from __future__ import print_function

import collections

import pytest

import restnavigator.utils as RNU

# pylint: disable=E1101

@pytest.fixture
def blank(request):
    '''Returns a blank object class with settable attributes'''
    class Blank(object):
        def __init__(self, **kwargs):
            self._kwargs = {}
            for k, v in kwargs.iteritems():
                setattr(self, k, v)
                self._kwargs[k] = v
            self._kwargs = kwargs
        def __repr__(self):
            r = ['{}={}'.format(k, v) for k, v in self._kwargs.iteritems()]
            return 'Blank({})'.format(' '.join(r))
    return Blank

def test_fix_scheme():
    assert RNU.fix_scheme('http://www.example.com') == 'http://www.example.com'
    assert RNU.fix_scheme('https://www.example.com') == \
        'https://www.example.com'
    assert RNU.fix_scheme('www.example.com') == 'http://www.example.com'
    with pytest.raises(ValueError):
        RNU.fix_scheme('ftp://www.example.com')
    with pytest.raises(ValueError):
        RNU.fix_scheme('http://http://www.example.com')


def test_normalize_getitem_args():
    nga = RNU.normalize_getitem_args
    assert nga('foo') == (['foo'], {}, False, False)
    assert (nga(slice('bar', 'baz'))
            == ([], {'bar': 'baz'}, False, False))
    assert (nga(('gax', slice('qux', 'foo')))
            == (['gax'], {'qux': 'foo'}, False, False))
    assert (nga((slice('foo', 'bar'), slice('baz', 'qux')))
            == ([], {'foo': 'bar', 'baz': 'qux'}, False, False))
    assert nga(slice(None)) == ([], {}, True, False)
    assert nga((Ellipsis, slice(None))) == ([], {}, True, True)
    assert (nga(('gax', slice('foo', 'bar'), Ellipsis))
            == (['gax'], {'foo':'bar'}, False, True))


def test_slice_process():
    assert RNU.slice_process(slice('a','b', None)) == {'a':'b'}
    assert RNU.slice_process(slice('a', None, None)) == {'a': ''}
    with pytest.raises(ValueError):
        RNU.slice_process(slice(None,'b', None))


@pytest.mark.parametrize(('root_uri', 'expected'), [
    ('http://www.example.com', 'Example'),
    ('www.example.com', 'Example'),
    ('www.example.com/', 'Example'),
    ('www.example.net', 'ExampleNet'),
    ('www.example.io', 'ExampleIO'),
    ('api.example.com', 'ExampleAPI'),
    ('fsgqwe.example.com', 'FsgqweExample'),
    ('www.example.com/api', 'ExampleAPI'),
    ('api.example.com/api/', 'ExampleAPI'),
    ('api.example.com/api?api=', 'ExampleAPI'),
    ('example.com/squid/api/yams', 'ExampleSquidYamsAPI'),
    ('example.com/v2/', 'Example.v2'),
    ('example.com/v0.0.1/', 'Example.v0.0.1'),
    ('example.com/gov2013', 'ExampleGov2013'),  # happens to have v2013 in it
    ('example.com?api=v2,x=3', 'ExampleX3API.v2'),
    ('googleapis.com/language/translate/v2', 'GoogleAPIsLanguageTranslate.v2'),
    ('haltalk.herokuapp.com/', 'Haltalk'),  # special case herokuapp.com
    ('fooexample.appspot.com', 'Fooexample'),  # special case appspot.com
    ('example.com/ko%C5%BEu%C5%A1%C4%8Dek', 'ExampleKozuscek'),
    ('example.com/%E3%82%AF%E3%83%AA%E3%83%BC%E3%82%AC%E3%83%BC',
     'ExampleKuriga'),
])
def test_namify(root_uri, expected):
    assert RNU.namify(root_uri) == expected


def test_LinkList__append_with_get_by_one(blank):
    linklist = RNU.LinkList()
    obj = blank()
    linklist.append_with(obj, name='myobject', title='My Object')
    assert linklist.get_by('name', 'myobject') == obj
    assert linklist.get_by('title', 'My Object') == obj

def test_LinkList__getby_failure():
    ll = RNU.LinkList()
    assert ll.get_by('name', 'XXX') is None

@pytest.fixture
def linklist(blank):
    linklist = RNU.LinkList()
    objs = collections.OrderedDict([
        ('A.a', blank(name='A.a', klass='A', id='a')),
        ('A.b', blank(name='A.b', klass='A', id='b')),
        ('A.c', blank(name='A.c')),
        ('B.a', blank(name='B.a', klass='B', id='a')),
        ('B.b', blank(id='b')),
        ('C.a', blank(name='C.a', klass='C', id='a')),
        ('C.b', blank(klass='C', id='b')),
    ])
    for i, obj in enumerate(objs.values()):
        linklist.append_with(obj, **obj._kwargs)
    return linklist, objs

def test_LinkList__get_by_1(linklist):
    ll, objs = linklist
    assert ll.get_by('name', 'A.a') == objs['A.a']

def test_LinkList__get_by_2(linklist):
    ll, objs = linklist
    assert ll.get_by('klass', 'A') == objs['A.a']

def test_LinkList__getall_by_name(linklist):
    ll, objs = linklist
    assert ll.getall_by('name', 'A.a') == [objs['A.a']]
    assert ll.getall_by('name', 'A.b') == [objs['A.b']]
    assert ll.getall_by('name', 'A.c') == [objs['A.c']]
    assert ll.getall_by('name', 'B.a') == [objs['B.a']]
    assert ll.getall_by('name', 'B.b') == []
    assert ll.getall_by('name', 'C.a') == [objs['C.a']]
    assert ll.getall_by('name', 'C.b') == []
    assert ll.getall_by('name', 'D.a') == []

def test_LinkList__getall_by_klass(linklist):
    ll, objs = linklist
    assert ll.getall_by('klass', 'A') == [objs['A.a'], objs['A.b']]
    assert ll.getall_by('klass', 'B') == [objs['B.a']]
    assert ll.getall_by('klass', 'C') == [objs['C.a'], objs['C.b']]
    assert ll.getall_by('klass', 'D') == []

def test_LinkList__getall_by_id(linklist):
    ll, objs = linklist
    assert ll.getall_by('id', 'a') == [objs['A.a'], objs['B.a'], objs['C.a']]
    assert ll.getall_by('id', 'b') == [objs['A.b'], objs['B.b'], objs['C.b']]
    assert ll.getall_by('id', 'c') == []
    assert ll.getall_by('id', 'd') == []

def test_LinkList__init_iterator(linklist):
    ll_iterated, objs = linklist
    ctor_arg = [(v, v._kwargs) for k, v in objs.iteritems()]
    ll_ctor = RNU.LinkList(ctor_arg)
    assert ll_iterated == ll_ctor
    # Non black-box test warning!
    assert ll_iterated._meta == ll_ctor._meta

@pytest.fixture
def unhashable_prop():
    bad_value = ['bad_stuff']
    prop_list = [('A', {'hi': 'there'}), ('B', {'bad': bad_value})]
    return prop_list, bad_value


def test_LinkList__get_by_unhashable_is_string(unhashable_prop):
    prop_list, bad_value = unhashable_prop
    test_list = RNU.LinkList(prop_list)
    assert test_list.get_by('bad', str(bad_value)) == 'B'

def test_LinkList__get_by_unhashable(unhashable_prop):
    prop_list, bad_value = unhashable_prop
    test_list = RNU.LinkList(prop_list)
    assert test_list.get_by('bad', bad_value) == 'B'

def test_LinkList__getall_by_unhashable(unhashable_prop):
    prop_list, bad_value = unhashable_prop
    test_list = RNU.LinkList(prop_list)
    assert test_list.getall_by('bad', bad_value) == ['B']

def test_LinkList__named_unhashable():
    bad_value = {'totally': ['bad', 'key']}  # This normally should be hashable
    prop_list = [('STILL_GOT_IT', {'name': bad_value})]
    test_list = RNU.LinkList(prop_list)
    assert test_list.named(bad_value) == 'STILL_GOT_IT'

def test_LinkList__get_by_unicode_valu():
    unicode_value = u'クリーガーさんは、私の桜がしおれている！'
    prop_list = [('VALUE', {'title': unicode_value})]
    test_list = RNU.LinkList(prop_list)
    assert test_list.get_by('title', unicode_value) == 'VALUE'
