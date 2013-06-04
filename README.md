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

To begin interacting with a restful api, you've got to create a HALNavigator
that points to the api root. Ideally, in a restful API, the root URL is the only
URL that needs to be hardcoded in your application. All other URLs are obtained
from the api responses themselves.

As an example, we'll connect to the haltalk api.

```python
>>> from rest_navigator import HALNavigator
>>> N = HALNavigator('http://haltalk.herokuapp.com/', name="haltalk")
>>> N
HALNavigator:haltalk
```

Usually, with the index, the data isn't too important, rather the links it gives
you are important. Let's look at those:

```python
>>> N.links()
{'ht:users': [HALNavigator(haltalk.users)],
 'ht:signup': [HALNavigator(haltalk.signup)],
 'ht:me': [HALNavigator(haltalk.users.{name})],
 'ht:latest-posts': [HALNavigator(haltalk.posts.latest)]
}
```

Here we can see that the links are organized by their relation type (the key),
and each key corresponds to a new HALNavigator that represents some other
resource. Relation types are extremely important in restful apis: we need them
to be able to be able to mechanistically determine what a link means in relation
to the current resource.

In addition, the root has some state associated with it which you can get in two
different ways:

```python
>>> N.state # Nothing since resource has not been fetched yet
>>> objson = N()
>>> objson
{u'hint_1': u'You need an account to post stuff..',
 u'hint_2': u'Create one by POSTing via the ht:signup link..',
 u'hint_3': u'Click the orange buttons on the right to make POST requests..',
 u'hint_4': u'Click the green button to follow a link with a GET request..',
 u'hint_5': u'Click the book icon to read docs for the link relation.',
 u'welcome': u'Welcome to a haltalk server.'}
>>> state2 = N.state  # Now the state is present
{u'hint_1': u'You need an account to post stuff..',
 u'hint_2': u'Create one by POSTing via the ht:signup link..',
 u'hint_3': u'Click the orange buttons on the right to make POST requests..',
 u'hint_4': u'Click the green button to follow a link with a GET request..',
 u'hint_5': u'Click the book icon to read docs for the link relation.',
 u'welcome': u'Welcome to a haltalk server.'}
```

Calling a HALNavigator will execute a GET request against the resource and returns
its value (which it will cache). The only difference is that repeated calls of
the navigator will get copies of the state dictionary, whereas the .state
attribute is the same dictionary (so modify it at your own peril!)

Let's register a hal talk account. Unfortunately, we don't really know how to do
that, so let's look at the documentation. The `ht:signup` link looks promising,
let's check that:

```python
>>> N.docsfor('ht:signup') # a browser opens http://haltalk.herokuapp.com/rels/signup
```

What? Popping up a browser from a library call? Yes, that's how rest_navigator
rolls. You see, the docs are for humans, and while custom rel-types are URIs,
they shouldn't automatically be dereferenced by a program that interacts with
the api. So popping up a browser serves two purposes:

  1. It allows easy access to the documentation at the time when you most need
  it: when you're mucking about in the command line trying to figure out how to
  interact with the api.
  2. It reminds you not to try to automatically dereference the rel
  documentation and parse it in your application.

If you need a more robust way to browse the api and the documentation,
[HAL Browser](https://github.com/mikekelly/hal-browser) is probably your best
bet.

From the docs for `ht:signup` we find out the format for the POST request to
sign up. So let's actually sign up:

```python
>>> N['ht:signup'].post(
... {'username': 'fred23',
...  'password': 'some_passwd',
...  'real_name': my_real_name}
... ).status
(201, 'Created')
```

If the user name had already been in use, a 400 would have been returned from
the haltalk api. Using the Zen of Python guideline "Errors should never pass
silently." an exception would have been raised on a 400 or 500 status code. You
can squelch this exception and just have the post call return a HALNavigator
with a 400/500 status code if you want:

```python
>>> errNav = N['ht:signup'].post({
...    'username': 'fred',
...    'password': 'pwnme',
...    'real_name': 'Fred Wilson'
... }, raise_exc=False)
>>> errNav
HALNavigator('haltalk')['ht:signup']#400!
>>> errNav.status
(400, 'Bad Request')
>>> errNav.state
{"errors": {"username": ["is already taken"]}}
```

Now that we've signed up, lets take a look at our profile. The link for a user's
profile is a templated link, which we can tell because its repr has a '*'
character after it. You can also tell by the .parameters attribute:

```python
>>> N['ht:me']
HALNavigator('haltalk')['ht:me']*
>>> N['ht:me'].parameters
set(['name'])
```

The documentation for the `ht:me` rel type should tell us how the name parameter
is supposed to work, but in this case it's fairly obvious. There are two ways
you can input template parameters. Both are equivalent, but people may prefer
one over the other for aesthetic reasons:

```python
>>> N['ht:me'].uri
'/users/{name}'
>>> Nme_v1 = N['ht:me', 'name':'fred23']
>>> Nme_v1
HALNavigator('haltalk')['ht:me', 'name':'fred23']
>>> Nme_v2 = N['ht:me'].expand(name='fred23')  # equivalent to Nme_v1
>>> Nme_v2()
{'bio': None,
 'real_name': 'Fred Savage',
 'username': 'fred23'}
```

rest_navigator also makes it easy to iter


## More:

* You can specify a curie as a default namespace. As long as the curie is
  defined on the resource you want, you don't need to specify it when indexing link rels
* You can add hooks for different types, rels and profiles. If a link has one of
  these properties, it will call your hook when doing a server call.
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
* You can grab the HTTP headers with the .headers attribute
