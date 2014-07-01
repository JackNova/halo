import inspect
from flask import current_app
from instagram import client, subscriptions, InstagramAPIError, \
        InstagramClientError

"""
Instagram doesn't send back rate limit info with responses like twitter. So
we need to keep track of the number of requests made.

From the documentation:

    If you're sending too many requests too quickly, we'll send back a 503
    error code (server unavailable).

    You are limited to 5000 requests per hour per access_token or client_id overall.

1) InstagramClientError is raised if you supply invalid parameters to the method
or if the library is unable to parse the response.

2) InstagramAPIError is raised when instagram returns an error such as when you are
being rate limited.
"""

#def _get_method_class(meth):
#    """Gets the class that the method was defined in
#    """
#    for cls in inspect.getmro(meth.im_class):
#        if meth.__name__ in cls.__dict__: return cls
#    return None

class InstagramProxy(object):
    def __init__(self, account, app=current_app):
        self.api = client.InstagramAPI(
            access_token=account.access_token_key)

    def finish(self, account, save=False):
        # TODO: save rate limits?

        if save:
            account.save()

    def __getattr__(self, name):
        """Called if attribute not found in usual ways.
        TODO: Wrap all calls so that we can keep track of rate limits
        """
        # TODO: track number of calls in second
        return getattr(self.api, name)

# alias
Instagram = InstagramProxy
