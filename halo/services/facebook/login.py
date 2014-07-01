import logging, urllib, urllib2, cgi
from flask import request, current_app, json
import facebook

def trim_profile(profile):
    return profile

def redirect_or_access_token(
    callback,
    fields=['id', 'name', 'first_name', 'last_name', 'locale', 'picture', 'link']):

    oauth_code = request.args.get('code')

    config = current_app.config

    if oauth_code:
        args = dict(
            client_id=config['FACEBOOK_APP_ID'],
            redirect_uri=callback,
            client_secret=config['FACEBOOK_APP_SECRET'],
            code=oauth_code,
        )
        response = cgi.parse_qs(urllib2.urlopen(
            'https://graph.facebook.com/oauth/access_token?' +
            urllib.urlencode(args)).read())

        access_token = response['access_token'][-1]
        profile = json.load(urllib2.urlopen(
            'https://graph.facebook.com/me?' + \
            urllib.urlencode(dict(access_token=access_token, fields=fields))))
        return (access_token, None, profile)
    else:
        return 'https://graph.facebook.com/oauth/authorize?' + \
            urllib.urlencode({
                'client_id': config['FACEBOOK_APP_ID'],
                'redirect_uri': callback,
            })


