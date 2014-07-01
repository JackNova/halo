import logging
from flask import request, current_app
from instagram import client

"""
Instagram permissions:
- basic - to read any and all data related to a user (e.g. following/followed-by lists, photos, etc.) (granted by default)
- comments - to create or delete comments on a user.s behalf
- relationships - to follow and unfollow users on a user.s behalf
- likes - to like and unlike items on a user.s behalf
"""

#def trim_profile(profile):
#    return profile

def redirect_or_access_token(callback, scope=['likes', 'relationships']):
    """Returns the redirect url for authorization with instagram,
    or a tuple containing the access token key, secret, and profile
    depending on where we are in authorization flow.
    """
    oauth_code = request.args.get('code')

    config = current_app.config
    api = client.InstagramAPI(
        client_id=config['INSTAGRAM_CLIENT_ID'],
        client_secret=config['INSTAGRAM_CLIENT_SECRET'],
        redirect_uri=callback)
    redirect_url = api.get_authorize_url(scope=scope)

    if oauth_code:
        logging.debug(oauth_code)
        access_token, profile = api.exchange_code_for_access_token(oauth_code)
        return (access_token, None, profile)
    else:
        return redirect_url
