from __future__ import print_function
from __future__ import unicode_literals

import pytest

import rest_navigator.utils as RNU


def test_fix_scheme():
    assert RNU.fix_scheme('http://www.example.com') == 'http://www.example.com'
    assert RNU.fix_scheme('www.example.com') == 'http://www.example.com'
    with pytest.raises(ValueError):
        RNU.fix_scheme('ftp://www.example.com')
    with pytest.raises(ValueError):
        RNU.fix_scheme('http://http://www.example.com')


def test_normalize_getitem_args():
    assert RNU.normalize_getitem_args('foo') == (['foo'], {})
    assert RNU.normalize_getitem_args(slice('bar', 'baz')) == ([], {'bar': 'baz'})
    assert (RNU.normalize_getitem_args(('gax', slice('qux', 'foo')))
            == (['gax'], {'qux': 'foo'}))
    assert (RNU.normalize_getitem_args((slice('foo', 'bar'), slice('baz', 'qux')))
            == ([], {'foo': 'bar', 'baz': 'qux'}))


def test_slice_process():
    assert RNU.slice_process(slice('a','b', None)) == {'a':'b'}
    assert RNU.slice_process(slice('a', None, None)) == {'a': ''}
    with pytest.raises(ValueError):
        RNU.slice_process(slice(None,'b', None))
    with pytest.raises(ValueError):
        RNU.slice_process(slice(None, None, None))
