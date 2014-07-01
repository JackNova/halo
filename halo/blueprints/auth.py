import logging, urllib, json
from flask import Blueprint, request, render_template, redirect, session, \
        g, url_for, current_app, abort, json
from blinker import Namespace
from halo.util.endpoints import userid_from_request, make_auth_token
from models import User, Account

my_signals = Namespace()
account_added = my_signals.signal('account-added')
logged_in = my_signals.signal('logged-in')

# flow:
# 1) get authorization url from twitter and redirect to it
# 2) on success twitter redirects user back to authorize url with
# an tokens required to get access token
# 3) get access token from twitter redirect user to return_url

auth = Blueprint('my_auth', __name__) # "auth" is taken by flask_peewee

# TODO: custom error page for 402's

"""
With oauth/authenticate: if the user is signed into twitter.com and has previously authorized the application to access their account they will be silently redirected back to the app.

With oauth/authorize: the user will see the allow screen regardless if they have previously authorized the app.

Force login forces the user to enter their credentials to ensure the correct users account is authorized.
"""

# optional arguments you can pass to connect method using query string in url
# TODO: get rid of this and just rely on LOGIN_SERVICES
LOGIN_REQUEST_ARGS = {
    'twitter': [
        ('authenticate', 'false'),
        ('force_login', 'false')
    ],
    # TODO: allow scope?
    'instagram': [],
}

@auth.after_request
def no_cache(resp):
    """Make sure auth requests aren't cached
    """
    resp.cache_control.no_cache = True
    return resp

@auth.route('/success/')
def success():
    """This endpoint is useful for login dialogs that monitor urls for successful
    callbacks, and retrieve auth token from url params and then close dialog
    immediately."""
    return ''

@auth.route('/<service>/login/', endpoint='login')
@auth.route('/<service>/add-account/', endpoint='add_account')
def connect(service):
    """Params: authenticate, force_login, return_url, platform (required)"""
    #return redirect('https://instagram.com/accounts/logout/')

    login_args = {}
    for key, default_value in LOGIN_REQUEST_ARGS.get(service, []):
        login_args[key] = request.args.get(key, default_value) == 'true'
    #authenticate = request.args.get('authenticate', 'false') == 'true'
    #force_login = request.args.get('force_login', 'false') == 'true'
    add_account = 'add-account' in request.path

    services = User.ADD_ACCOUNT_SERVICES if add_account else \
            User.LOGIN_SERVICES

    if not services or not service in services:
        logging.debug('%s not supported' % service)
        raise abort(404)

    login = services[service]
    logging.debug('Callback url: %s' % request.base_url)
    result = login.redirect_or_access_token(request.base_url, **login_args)

    if isinstance(result, str):
        # we are at redirect to authorization url portion of flow
        redirect_url = result
        session['user_id'] = userid_from_request(fail_silently=True)
        session['device_id'] = request.args.get('device_id')
        session['return_url'] = request.args.get('return_url')
        # TODO: nice error message when platform key is not found
        session['platform'] = request.args['platform']
        # application is an optional param
        session['app_id'] = request.args.get('app_id', '')
        return redirect(redirect_url)

    # use has authorized and we have access token
    access_token_key, access_token_secret, profile = result
    user_id = session.pop('user_id')
    device_id = session.pop('device_id')
    return_url = session.pop('return_url')
    platform = session.pop('platform')
    app_id = session.pop('app_id')

    #profile = login.get_profile(access_token_key, access_token_secret)
    account_id = profile['id']

    try:
        if add_account:
            user = User.connect_user_account(
                id=user_id,
                account_id=account_id,
                service=service,
                access_token_key=access_token_key,
                access_token_secret=access_token_secret,
                profile=profile,
            )
        else:
            user = User.login_with_account(
                account_id=account_id,
                service=service,
                device_id=device_id,
                platform=platform,
                access_token_key=access_token_key,
                access_token_secret=access_token_secret,
                profile=profile,
                app_id=app_id or None,
            )
    except User.FeatureNotSupported, e:
        raise abort(403, e.message)
    except User.DoesNotExist, e:
        raise abort(404, 'User not found')

    if platform == 'Web':
        session['user'] = user.id
        auth_token = None
    else:
        # the auth token is required for accessing api functions on mobile
        auth_token = make_auth_token(user.id)

    signal = account_added if add_account else logged_in
    signal.send(current_app._get_current_object(),
                user=user, account_id=account_id,
                service=service)

    if return_url:
        account = Account.select().where(
            (Account.id==account_id) & (Account.service==service)).get()

        # specify return url if not in popup
        fragment = urllib.urlencode({
            'auth_token': auth_token,
            'account': json.dumps(account.__jsonify__()),
            #'account': json.dumps(login.trim_profile(profile)),
        })
        logging.debug(fragment)
        return_url += '&' + fragment if '?' in return_url else '?' + fragment
        return redirect(return_url)
    else:
        # template will call parent popup to add new account
        # or will pass account data to parent by triggering a url
        # change in phonegap
        return render_template('auth/success.html',
                               user=user,
                               device_id=device_id,
                               profile=login.trim_profile(profile),
                               auth_token=auth_token,
                               platform=platform,
                               add_account=add_account)
