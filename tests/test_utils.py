from __future__ import print_function
from __future__ import unicode_literals

import pytest

import rest_navigator.utils as RNU

# pylint: disable=E1101


def test_fix_scheme():
    assert RNU.fix_scheme('http://www.example.com') == 'http://www.example.com'
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
    ('fooexample.appspot.com', 'Fooexample')  # special case appspot.com
])
def test_namify(root_uri, expected):
    assert RNU.namify(root_uri) == expected
