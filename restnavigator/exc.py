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
        "The resource at {} wasn't valid JSON:\n\n\n{}".format(
            self.uri, self.response)
