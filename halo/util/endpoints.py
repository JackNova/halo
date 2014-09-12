import time, datetime, json, logging
from functools import wraps
from peewee import Model
from flask import session, current_app, request, abort, g, Response
from itsdangerous import URLSafeSerializer
from models import User

try:
    from models import UserAccount
except ImportError:
    pass

#
# DECORATORS
#

def requires_api(cls, finish=True, save_account=False):
    """Pass a class from halo.services. Place this decorator
    after requires_user
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'api'):
                g.api = cls(g.account)
            if save_account:
                g.save_account = True
            try:
                return f(*args, **kwargs)
            finally:
                if finish:
                    g.api.finish(g.account)
        return decorated
    return decorator

def requires_user(account=False, all_accounts=False, key='id',
                  fail_silently=False, save_account=False,
                  main_account=False):
    """Fetch user and account(s) from database and put on flask global.
    key is the url route variable to use as the account id.
    """
    # TODO: accounts could get out of sync if multiple ways of fetching accounts set
    #(e.g. if all_accounts, account, and main_account are all set)
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            assert not (account and all_accounts), 'Ambiguous arguments'

            # will raise a 500 error if headers not found
            #g.platform = request.headers['Platform']

            if not getattr(g, 'save_account', False):
                g.save_account = save_account

            if hasattr(g, 'user') and \
               (not account or hasattr(g, 'account')) and \
               (not all_accounts or hasattr(g, 'accounts')) and \
               (not main_account or hasattr(g, 'main_account')):
                return f(*args, **kwargs)

            g.user_id = userid_from_request()

            if account:
                # flask always passes url variables as keyword arguments
                g.account_id = kwargs[key]#request.headers.get('Account')
            else:
                g.account_id = None

            try:
                if account:
                    g.user, g.account = UserAccount.from_user_account(
                        g.user_id, g.account_id)
                elif all_accounts:
                    g.user, g.accounts = UserAccount.from_user(g.user_id)
                else:
                    g.user = User.select().where(User.id == g.user_id).get()

                if main_account and not hasattr(g, 'main_account'):
                    # TODO: catch errors if key not found
                    main_account_id = request.headers['Account']
                    #main_account_service = request.headers['Service']
                    if account and g.account_id == main_account_id:
                        g.main_account = g.account
                    elif all_accounts:
                        for acct in g.accounts:
                            if str(acct.id) == main_account_id:
                                g.main_account = acct
                                break

                    if not hasattr(g, 'main_account'):
                        _, g.main_account = UserAccount.from_user_account(
                            g.user_id, main_account_id)

            except (UserAccount.DoesNotExist, User.DoesNotExist), e:
                logging.warning('User %s, account %s not found: %s' % \
                                (g.user_id, g.account_id, e))
                if not fail_silently:
                    raise abort(401, 'Not logged in')
            except:
                if not fail_silently:
                   raise

            try:
                return f(*args, **kwargs)
            finally:
                if g.save_account:
                    if hasattr(g, 'account'):
                        g.account.save()
                    if hasattr(g, 'all_accounts'):
                        for acct in g.accounts:
                            acct.save()

                g.save_account = False

        return decorated
    return decorator

#
# FUNCTIONS
#

def _dthandler(obj):
    if isinstance(obj, datetime.datetime):
        return time.mktime(obj.timetuple())
    if isinstance(obj, Model):
        if hasattr(obj, '__jsonify__'):
            return obj.__jsonify__()

def jsonify(__model__=None, **data):
    """Like flask's jsonify but status code of response can be set,
    and can handle datetime serialization.
    """
    if __model__ is not None:
        data = dict(__model__.__jsonify__(), **data)
    resp = Response(json.dumps(data, default=_dthandler),
                    mimetype='application/json')
    #if not status_code == None:
    #    resp.status_code = status_code
    return resp

# TODO: get rid of this (deprecated, use jsonify instead)
def jsonify_status_code(status_code, *args, **kw):
    """Returns a jsonified response with the specified HTTP status code.
    Call this method with just status code to return response with no content.
    """
    resp = jsonify(*args, **kw)
    resp.status_code = status_code
    return resp

def userid_from_request(fail_silently=False):
    """Will get user id from secure cookie, header, or url param"""
    if 'user' in session:
        return session['user']
    else:
        if 'auth_token' in request.args:
            auth_token = request.args.get('auth_token')
        #elif 'uid' in request.args:
        #    auth_token = request.args.get('uid')
        else:
            auth_token = request.headers.get('Auth-Token')

        if not auth_token:
            if fail_silently:
                return None
            else:
                raise abort(400)

        config = current_app.config
        s = URLSafeSerializer(config['SECRET_KEY'])
        return s.loads(auth_token)

def make_auth_token(user_id):
    try:
        config = current_app.config
    except RuntimeError:
        # could happen if called out of request
        from app import app
        config = app.config

    s = URLSafeSerializer(config['SECRET_KEY'])
    return s.dumps(str(user_id))

def admin_http_auth():
    auth = request.authorization
    if not auth or \
       not admin_check_credentials(auth.username, auth.password):
        return admin_return_authenticate()

def admin_check_credentials(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    config = current_app.config
    return username == config['ADMIN_USER'] and \
            password == config['ADMIN_PASSWORD']

def admin_return_authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def allow_crossdomain(app,
                      methods='GET, POST, UPDATE, PUT, OPTIONS, DELETE, PATCH',
                      headers='Content-Type',
                      max_age='21600',
                      origin='*'):
    def func(resp):
        default_options_resp = current_app.make_default_options_response()

        if request.method == 'OPTIONS':
            resp = default_options_resp

        h = resp.headers
        h['Access-Control-Allow-Origin'] = origin
        h['Access-Control-Allow-Methods'] = default_options_resp.headers.get(
            'allow', methods)
        h['Access-Control-Max-Age'] = max_age
        h['Access-Control-Allow-Headers'] = headers

        return resp

    app.after_request(func)
