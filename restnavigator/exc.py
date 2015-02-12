from __future__ import print_function


class WileECoyoteException(ValueError):
    '''Raised when a url has a bad scheme'''
    pass


class ZachMorrisException(ValueError):
    '''Raised when a url has too many schemes'''
    pass


class HALNavigatorError(Exception):
    '''Raised when a response is an error

    Has all of the attributes of a normal HALNavigator. The error body can be
    returned by examining response.body '''

    def __init__(self, message, nav=None, status=None, response=None):
        self.nav = nav
        self.response = response
        self.message = message
        self.status = status
        super(HALNavigatorError, self).__init__(message)


class NoResponseError(ValueError):
    '''Raised when accessing a field of a navigator that has not
    fetched a response yet'''
    pass


class UnexpectedlyNotJSON(TypeError):
    '''Raised when a non-json parseable resource is gotten'''

    def __init__(self, uri, response):
        self.uri = uri
        self.response = response

    def __repr__(self):  # pragma: nocover
        return "The resource at {0} wasn't valid JSON:\n\n\n{1}".format(
            self.uri, self.response)


class OffTheRailsException(TypeError):
    '''Raised when a traversal specified to __getitem__ cannot be
    satisfied
    '''
    def __init__(self, traversal, index, intermediates, e):
        self.traversal = traversal
        self.index = index
        self.intermediates = intermediates
        self.exception = e

    def _format_exc(self):
        if isinstance(self.exception, KeyError):
            return "{0!r} doesn't have the rel {0!r}".format(
                self.intermediates[-1], self.exception[0])
        else:
            return self.exception[0]

    def __repr__(self):  # pragma: nocover
        ("Attempted to traverse from {0!r} using the traversal {1!r}, "
         "but failed on part {2} because {3}.").format(
             self.intermediates[0],
             self.traversal,
             self.index + 1,
             self.msg)
