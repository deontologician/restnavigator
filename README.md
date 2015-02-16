# REST Navigator

[![Build Status](https://travis-ci.org/deontologician/rest_navigator.png?branch=master)](https://travis-ci.org/deontologician/rest_navigator)
[![Coverage Status](https://img.shields.io/coveralls/deontologician/rest_navigator/next.svg)](https://coveralls.io/r/deontologician/rest_navigator?branch=next)

REST Navigator is a python library for interacting with hypermedia apis ([REST level 3][]).
Right now, it only supports [HAL+JSON][] but it should be general enough to extend to other formats eventually.
Its first goal is to make interacting with HAL hypermedia apis as painless as possible, while discouraging REST anti-patterns.

[REST level 3]: http://martinfowler.com/articles/richardsonMaturityModel.html#level3
[HAL+JSON]: http://tools.ietf.org/html/draft-kelly-json-hal-05

## Contents

- [How to use it](#how-to-use-it)
    - [Links](#links)
    - [GET requests](#get-requests)
    - [Link relation docs](#link-relation-docs)
    - [POST requests](#post-requests)
    - [Errors](#errors)
    - [Templated links](#templated-links)
    - [Authentication](#authentication)
- [Additional Topics](#additional-topics)
    - [Identity Map](#identity-map)
    - [Iterating over a Navigator](#iterating-over-a-navigator)
    - [Headers (Request vs. Response)](#headers-request-vs-response)
    - [Bracket mini-language](#bracket-minilanguage)
    - [Finding the right link](#finding-the-right-link)
    - [Default curie](#default-curie)
- [Development](#development)
    - [Testing](#testing)
    - [Planned for the future](#planned-for-the-future)

<!-- end toc -->

## How to use it

To begin interacting with a HAL api, you've got to create a HALNavigator that points to the api root.
Ideally, in a hypermedia API, the root URL is the only URL that needs to be hardcoded in your application.
All other URLs are obtained from the api responses themselves (think of your api client as 'clicking on links', rather than having the urls hardcoded).

As an example, we'll connect to the haltalk api.

```python
>>> from restnavigator import HALNavigator
>>> N = HALNavigator('http://haltalk.herokuapp.com/', apiname="haltalk")
>>> N
HALNavigator(haltalk)
```

### Links

Usually, with the index (normally at the api root), you're most interested in the links.
Let's look at those:

```python
>>> N.links
{'ht:users': [HALNavigator(haltalk.users)],
 'ht:signup': [HALNavigator(haltalk.signup)],
 'ht:me': [HALNavigator(haltalk.users.{name})],
 'ht:latest-posts': [HALNavigator(haltalk.posts.latest)]
}
```

(This may take a moment because asking for the links causes the HALNavigator to actually request the resource from the server).

Here we can see that the links are organized by their relation type (the key), and each key corresponds to a new HALNavigator that represents some other resource.
Relation types are extremely important in restful apis: we need them to be able to determine what a link means in relation to the current resource, in a way that is automatable.

### GET requests

In addition, the root has some state associated with it which you can get in two different ways:

```python
>>> N() # cached state of resource (obtained when we looked at N.links)
{u'hint_1': u'You need an account to post stuff..',
 u'hint_2': u'Create one by POSTing via the ht:signup link..',
 u'hint_3': u'Click the orange buttons on the right to make POST requests..',
 u'hint_4': u'Click the green button to follow a link with a GET request..',
 u'hint_5': u'Click the book icon to read docs for the link relation.',
 u'welcome': u'Welcome to a haltalk server.'}
>>> N.fetch() # will refetch the resource from the server
{u'hint_1': u'You need an account to post stuff..',
 u'hint_2': u'Create one by POSTing via the ht:signup link..',
 u'hint_3': u'Click the orange buttons on the right to make POST requests..',
 u'hint_4': u'Click the green button to follow a link with a GET request..',
 u'hint_5': u'Click the book icon to read docs for the link relation.',
 u'welcome': u'Welcome to a haltalk server.'}
```

Calling a HALNavigator will execute a GET request against the resource and returns its value (which it will cache).

### Link relation docs

Let's register a hal talk account.
Unfortunately, we don't really know how to do that, so let's look at the documentation.
The `ht:signup` link looks promising, let's check that:

```python
>>> N.docsfor('ht:signup')
```

A browser will open to http://haltalk.herokuapp.com/rels/signup.

What? Popping up a browser from a library call?
Yes, that's how rest_navigator rolls.
The way we see it: docs are for humans, and while custom rel-types are URIs, they shouldn't automatically be dereferenced by a program that interacts with the api.
So popping up a browser serves two purposes:

  1. It allows easy access to the documentation at the time when you most need it: when you're mucking about in the command line trying to figure out how to interact with the api.
  2. It reminds you not to try to automatically dereference the rel documentation and parse it in your application.

If you need a more robust way to browse the api and the documentation, [HAL Browser][] is probably your best bet.

[HAL Browser]: https://github.com/mikekelly/hal-browser

### POST requests

The docs for `ht:signup` explain the format of the POST request to sign up.
So let's actually sign up (Note: haltalk is a toy api for example purposes, don't ever send plaintext passwords over an unencrypted connection in a real app!):

```python
>>> fred23 = N['ht:signup'].create(
... {'username': 'fred23',
...  'password': 'some_passwd',
...  'real_name': 'Fred 23'}
... )
>>> fred23
HALNavigator(haltalk.users.fred23)
```

### Errors

If the user name had already been in use, a 400 would have been returned from the haltalk api.
rest_navigator follows the Zen of Python guideline "Errors should never pass silently".
An exception would have been raised on a 400 or 500 status code.
You can squelch this exception and just have the post call return a `HALNavigator` with a 400/500 status code if you want:

```python
>>> dup_signup = N['ht:signup'].create({
...    'username': 'fred23',
...    'password': 'pwnme',
...    'real_name': 'Fred Wilson'
... }, raise_exc=False)
>>> dup_signup
ErrorNavigator(haltalk.signup)  # 400!
>>> dup_signup.status
(400, 'Bad Request')
>>> dup_signup.state
{"errors": {"username": ["is already taken"]}}
```

### Templated links

Now that we've signed up, lets take a look at our profile.
The link for a user's profile is a templated link, which we can tell because its repr has `{}` in it.
You can also tell by the `.parameters` attribute:

```python
>>> N.links.keys()
['ht:latest-posts', 'ht:me', 'ht:users', 'ht:signup']
>>> N['ht:me']
HALNavigator(haltalk.users.{name})
>>> N['ht:me'].parameters
set(['name'])
```

The documentation for the `ht:me` rel type should tell us how the name parameteris supposed to work, but in this case it's fairly obvious (plug in the username).
There are two ways you can input template parameters.
Both are equivalent, but people may prefer one over the other for aesthetic reasons:

```python
>>> N['ht:me'].template_uri
'http://haltalk.herokuapp.com/users/{name}'
>>> Fred1 = N['ht:me', 'name':'fred23']
>>> Fred1
HALNavigator('haltalk.users.fred23')
>>> Fred2 = N['ht:me'].expand(name='fred23')  # equivalent to Fred1
>>> Fred2()
{'bio': None, 'real_name': 'Fred Wilson', 'username': 'fred23'}
>>> Fred1 is Fred2  # HALNavigator keeps an identity cache of resources
True
```

### Authentication

In order to post something to haltalk, we need to authenticate with our newly created account.
HALNavigator allows any [authentication method that requests supports][] (so OAuth etc).
For basic auth (which haltalk uses), we can just pass a tuple.

[authentication method that requests supports]: http://www.python-requests.org/en/latest/user/advanced/#custom-authentication

```python
>>> N.authenticate(('fred23', 'pwnme'))  # All subsequent calls are authenticated
```

Now we can actually create a new post:

```python
>>> N_post = N['ht:me', 'name':'fred23']['ht:posts'].create({'content': 'My first post'})
>>> N_post
HALNavigator(Haltalk.posts[523670eff0e6370002000001])
>>> N_post()
{'content': 'My first post', 'created_at': '2014-06-26T03:19:52+00:00'}
```

## Additional Topics

### Identity Map

You don't need to worry about inadvertently having two different navigators pointing to the same resource.
rest_navigator will reuse the existing navigator instead of creating a new one

### Iterating over a Navigator

If a resource has a link with the rel "next", the navigator for that resource can be used as a python iterator.
It will automatically raise a StopIteration exception if a resource in the chain does not have a next link.
This makes moving through paged resources really simple and pythonic:

```python
post_navigator = N['ht:posts']
for post in post_navigator:
    # the first post will be post_navigator itself
    print(post.state)
```

### Headers (Request vs. Response)

HTTP response headers are available in `N.response.headers`

Headers that will be sent on each request can be obtained through the session:

```python
>>> N.session.headers
# Cookies, etc
```

### Bracket mini-language

The bracket (`[]`) operator on Navigators has a lot of power.
As we saw earlier, the main use is to get a new Navigator from a link relation:

```python
>>> N2 = N['curie:link_rel']
```

But, it can also go more than one link deep, which is equivalent to using multiple brackets in a row:

```python
>>> N3 = N['curie:first_link', 'curie:second_link']
# equivalent to:
N3 = N['curie:first_link']['curie:second_link']
```

Another usage shown above is filling out templated links:

```python
>>> N['curie:posts'].template_uri
"http://example.com/api/posts{?page}"
>>> N['curie:posts'].templated
True
>>> N['curie:posts', 'page':3].uri
"http://example.com/api/posts?page=3"
>>> N['curie:posts'].expand(page=3).uri
"http://example.com/api/posts?page=3"
>>> N['curie:posts', 'page':3].templated
False
```

If you have a templated Navigator and you want to quickly fill in its template parameters with nothing, you can use this syntax:

```python
>>> N['curie:posts', :].templated
False
>>> N['curie:posts', :].uri
"http://example.com/api/posts"
```

Similarly, if you have a templated Navigator and would like to fill in some of the parameters but leave the other parameters for later:

```python
>>> N['curie:posts'].template_uri
"http://example.com/api/posts{?page,size}
>>> N['curie:posts', 'page':3]
"http://example.com/api/posts?page=3"
>>> N['curie:posts', page:3].templated
False
>>> N['curie:posts', page:3, ...].templated
True
>>> partial = N['curie:posts', page:3, ...]
>>> partial['size':12].uri
"http://example.com/api/posts?page=3,size=12"
```

These tricks aren't necessary all of the time, but they can be very handy in the right situation.

### Finding the right link

Normally, you can chain together brackets to jump from one resource to another in one go:

```python
>>> N['ht:widget']['ht:gadget']
```

This will return a Navigator for the `ht:widget` link relation and then immediately fetch the resource and return a Navigator for the `ht:gadget` link relation.
This works great if you have only one link per relation, but HAL allows multiple links per relation.
Say for instance we have some links like the following:

```javascript{
"ht:some_rel: [
    {
        "href": "/api/widget/1",
        "name": "widget1",
        "profile": "widget"
    },
    {
        "href": "/api/widget/2",
        "name": "widget2",
        "profile": "widget"
    },
    {
        "href": "/api/gadget/1",
        "name": "gadget1",
        "profile": "gadget"
    }
]
```

When we go to get the `ht:some_rel`, we'll get multiple results:
```python
>>> N['ht:some_rel']
[HALNavigator(api.widget[1]),
 HALNavigator(api.widget[2]),
 HALNavigator(api.gadget[1])]
```

How do we know which one is the one we want?
The [HAL spec] says links with the same rel can be disambiguated by the `name` link property:

[HAL spec]: https://tools.ietf.org/html/draft-kelly-json-hal-06#section-5.5

```python
>>> N.links['ht:some_rel'].get_by('name', 'gadget1')
HALNavigator(api.gadget[1])
>>> N.links['ht:some_rel'].named('gadget1')  # same as previous
HALNavigator(api.gadget[1])
```

We could also use other properties to slice and dice the list:

```python
>>> N.links['ht:some_rel'].get_by('profile', 'gadget')
HALNavigator(api.gadget[1])
>>> N.links['ht:some_rel'].getall_by('profile', 'widget')
[HALNavigator(api.widget[1]), HALNavigator(api.widget[2])]
```

This works for any property on links, not just the standard HAL properties.

### Default curie

You may specify a default curie when creating your Navigator:

```python
>>> N = HALNavigator('http://haltalk.herokuapp.com', curie='ht')
```

Now, when you follow links, you may leave off the default curie if you want:

```python
>>> N.links
{'ht:users': [HALNavigator(haltalk.users)],
 'ht:signup': [HALNavigator(haltalk.signup)],
 'ht:me': [HALNavigator(haltalk.users.{name})],
 'ht:latest-posts': [HALNavigator(haltalk.posts.latest)]
}
>>> N['ht:users']
HALNavigator(haltalk.users)
>>> N['users']
HALNavigator(haltalk.users)
```

The only exception is where the key being supplied is a [IANA registered link relation][], and there is a conflict (hint: this should be quite rare):

[IANA registered link relation]: http://www.iana.org/assignments/link-relations/link-relations.xhtml

```python
>>> N.links
{'ht:next': HALNavigator(haltalk.unregistered),
  'next': HALNavigator(haltalk.registered)}
>>> N['next']
HALNavigator(haltalk.registered)
```

## Development
### Testing
To run tests, first install the [pytest framework][]:

[pytest framework]: http://pytest.org/latest/getting-started.html

```
$ pip install -U pytest
```

To run tests, execute following from the root of the source directory:

```
$ py.test
```

### Planned for the future
* Ability to add hooks for different types, rels and profiles. If a link has one
  of these properties, it will call your hook when doing a server call.
* Take advantage of the "HTTP caching pattern" for embedded resources, and will
  treat embedded documents as permission not to dereference a link. Rest
  navigator handles this seamlessly underneath, so you don't have to worry about
  whether a resource is embedded or not.
* Since HAL doesn't specify what content type POSTs, PUTs, and PATCHes need to
  have, you can specify the hooks based on what the server will accept. This can
  trigger off either the rel type of the link, or rest navigator can do content
  negotiation over HTTP with the server directly to see what content types that
  resource will accept.
