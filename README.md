# REST Navigator

REST Navigator is a python library for interacting with
([level 3](http://martinfowler.com/articles/richardsonMaturityModel.html#level3))
HTTP REST apis with some defined hyperlinking relations. Initially, it only
supports [HAL+JSON](http://tools.ietf.org/html/draft-kelly-json-hal-05) but it
should be general enough to extend to other formats, and writing a navigator
that makes use of HTML links, or
[HTTP link-headers](http://tools.ietf.org/html/rfc5988) should be completely
feasible. It's first goal is making navigating HAL apis very painless, and
generality will come later.

# How to use it

To begin interacting with any api, you've got to create a Navigator that points
to the api root. As an example, we'll connect to the haltalk api.

    >>> from rest_navigator import Navigator
    >>> N = Navigator('http://haltalk.herokuapp.com/', name="haltalk")
    >>> N
    Navigator('haltalk')
    
Usually, with the index, the data isn't too important, rather the links it gives
you are important. Let's look at those:

    >>> N.links()
    {'ht:users': Navigator('haltalk')['ht:users'],
     'ht:signup': Navigator('haltalk')['ht:signup'],
     'ht:me': Navigator('haltalk')['ht:me']*,
     'ht:latest-posts': Navigator('haltalk')['ht:latest-posts']
    }

Here we can see that the links are organized by their relation type (the key),
and each key corresponds to a new Navigator that represents some other
resource. Let's dereference one of them:
    
    >>> N['ht:']()
    {
    
Notice there aren't any URIs here, that's on purpose. rest_navigator
makes working directly with URIs awkward, because you really shouldn't need to
handle them directly with a properly designed RESTful API.

## Some other goodies:

* You can specify a curie as a default namespace. As long as the curie is
  defined on the resource you want, you don't need to specify it when indexing link rels
* You can add hooks for different types, rels and profiles. If a link has one of
  these properties, it will call your hook.
* You don't need to worry about inadvertently having two different navigators
  pointing to the same resource. Both will use the same underlying representation
* Rest navigator takes advantage of the "HTTP caching pattern" for embedded
  resources, and will treat embedded documents as permission not to dereference
  a link. Rest navigator handles this seamlessly underneath, so you don't have
  to worry about whether a resource is embedded or not.
* If a resource has a link with the rel "next", the navigator for that resource
  can be used as a python iterator. It will automatically raise a StopIteration
  exception if a resource in the chain does not have a next link. This makes
  moving through paged resources really simple and pythonic.
* Since HAL doesn't specify what content type POSTs, PUTs, and PATCHes need to
  have, you can specify the hooks based on what the server will accept. This can
  trigger off either the rel type of the link, or rest navigator can do content
  negotiation over HTTP with the server directly to see what content types that
  resource will accept. Rest navigator comes with hooks for application/json,
  multipart/form-data, and application/x-www-form-urlencoded.
