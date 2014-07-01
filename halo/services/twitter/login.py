from urllib2 import HTTPError
from flask import request, current_app
from api import Twitter, OAuthHandler
from tweepy import TweepError

# TODO: in get_profile return it like so: id, profile

def trim_profile(profile):
    """Send only needed fields to the client to save bandwidth"""
    # fields that will be sent to client
    fields = set([
        'id',
        'followers_count',
        'location',
        'utc_offset',
        'statuses_count',
        'description',
        'friends_count',
        'profile_image_url',
        'notifications',
        'geo_enabled',
        'screen_name',
        'lang',
        'favourites_count',
        'name',
        'url',
        'time_zone',
        'protected',
        #'account_token',
    ])
    return dict((k, v) for k, v in profile.iteritems() if k in fields)

def get_profile(access_token_key, access_token_secret, trim=True):
    config = current_app.config
    auth = OAuthHandler(config['TWITTER_CONSUMER_KEY'],
                        config['TWITTER_CONSUMER_SECRET'])
    auth.set_access_token(access_token_key, access_token_secret)
    api = Twitter(auth)
    profile = api.verify_credentials()
    if trim:
        profile = trim_profile(profile)
    return profile

def redirect_or_access_token(callback, force_login=False,
                             authenticate=False):
    """Returns the redirect url for authorization with twitter,
    or a tuple containing the access token key and secret depending
    on where we are in authorization flow.
    """
    oauth_token = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')

    config = current_app.config
    auth = OAuthHandler(config['TWITTER_CONSUMER_KEY'],
                        config['TWITTER_CONSUMER_SECRET'],
                        callback=callback)
    redirect_url = auth.get_authorization_url(
        signin_with_twitter=authenticate)
    request_token = auth.request_token

    if oauth_verifier:
        auth.set_request_token(oauth_token, request_token.secret)
        try:
            access_token = auth.get_access_token(oauth_verifier)
        except TweepError as e:
            if isinstance(e.message, HTTPError):
                http_error = e.message
                raise ValueError(http_error.read())

        profile = get_profile(access_token.key, access_token.secret)
        return (access_token.key, access_token.secret, profile)
    else:
        if force_login:
            redirect_url += '&force_login=true'
        return redirect_url

