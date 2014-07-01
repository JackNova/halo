import logging
import flask, werkzeug.exceptions
from functools import wraps
from flask import Blueprint, request, session, g, current_app, jsonify
from werkzeug.datastructures import MultiDict
from wtforms import Form, validators, TextField, BooleanField, PasswordField
from blinker import Namespace
from models import User
from halo.util.stripe import stripe_sync, stripe_delete
from app import db

PLANS = User.PLANS.keys()

my_signals = Namespace()
email_changed = my_signals.signal('email-changed')

"""
This blueprint is meant to be used only on web platforms.
Endpoints follow the same response/status code conventions as in the api blueprint.

Routes
/ -> POST, PATCH, DELETE
/plan/ -> POST
"""

stripe_user = Blueprint('stripe_user', __name__)
subscriptions = stripe_user # alias for convenience

# FORMS

class BaseForm(Form):
    name = TextField(validators=[
        validators.Required('A name is required')])
    #last_name = TextField(validators=[
    #    validators.Required('A last name is required')])
    email = TextField(validators=[
        validators.Email('A valid email address is required'),
        validators.Required('An email address is required')])
    #notifications = BooleanField(default=True)

class SubscriptionForm(BaseForm):
    plan = TextField(validators=[validators.AnyOf(PLANS,
                         'Invalid plan, must be one of: %(values)s')])
    stripeToken = TextField(validators=[validators.Required('Checkout failed')])
    password = PasswordField(validators=[
        validators.Required('A password is required'),
        validators.Length(6, -1, 'Password must be at least 6 characters long')])
    confirm_password = PasswordField(validators=[
        validators.EqualTo('password', 'Confirm password does not match')])

class ModifyUserForm(Form):
    current_password = PasswordField()
    new_password = PasswordField(validators=[
        validators.Length(6, -1, 'Password must be at least 6 characters long'),
        validators.Optional()])
    email = TextField()
    name = TextField()
    plan = TextField()
    notifications = BooleanField()

class ChangePlanForm(Form):
    plan = TextField(validators=[validators.AnyOf(PLANS,
                         'Invalid plan, must be one of: %(values)s')])
    stripeToken = TextField(validators=[validators.Required('Checkout failed')])

# FUNCTIONS

def abort(status_code, description=None, **kwargs):
    try:
        flask.abort(status_code, description)
    except werkzeug.exceptions.HTTPException, exc:
        exc.__dict__.update(kwargs)
        raise

def jsonify_status_code(status_code, *args, **kw):
    """Returns a jsonified response with the specified HTTP status code.
    Call this method with just status code to return response with no content.
    """
    resp = jsonify(*args, **kw)
    resp.status_code = status_code
    return resp

# CUSTOM ERROR HANDLERS

@subscriptions.errorhandler(400)
@subscriptions.errorhandler(401)
def bad_request(e):
    """Forms should be validated client-side as well so that we rarely get
    a bad request.
    """
    message = e.description
    return jsonify_status_code(e.code, message=message)

@subscriptions.after_request
def no_cache(resp):
    """Make sure api requests aren't cached"""
    resp.cache_control.no_cache = True
    return resp

# DECORATORS

def requires_user(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            user_id = session['user']
            user = User.get(User.id == user_id)
        except (User.DoesNotExist, KeyError):
            session.clear()
            raise abort(401, 'User session expired')
        g.user = user
        return f(*args, **kwargs)
    return decorated

def process_form(form_class):
    """Validates form data, retrieves user from database, and returns a redirect
    or json response depending on presence of redirect_url param in url.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            g.raw_data = request.form or MultiDict(request.json)
            form = form_class(g.raw_data)

            # validate the form data
            if not form.validate():
                # this should never happen if doing client-side validation
                # before request
                message = form.errors.items()[0][1][0]
                raise abort(400, message)

            g.form_data = form.data

            return f(*args, **kwargs)

        return decorated
    return decorator

# ENDPOINTS

@subscriptions.route('/', methods=['POST'])
@process_form(SubscriptionForm)
@requires_user
def subscribe():
    """Subscribe to new plan and modify user attributes.
    """
    user = g.user
    data = g.form_data

    if user.plan:
        # user is already subscribed to a plan and should use /plan/ endpoint
        # to modify it
        message = 'You are already subscribed to a %s plan. \
                You can modify your plan under account settings.' % user.plan
        raise abort(400, message)

    # check if email is already used by another user
    if User.select().where(User.email == data['email']).count() > 0:
        raise abort(400, 'That email is already taken', field='email')

    stripe_plan = User.PLANS[data['plan']]['stripe']
    stripe_sync(user, stripe_plan=stripe_plan, plan=data['plan'],
                token=data['stripeToken'])

    new_email = not user.email == data['email']

    if new_email:
        user.email_confirmed = False

    # update user record
    user.email = data['email']
    user.first_name = data['first_name']
    user.last_name = data['last_name']
    user.set_password(data['password'])
    user.save()

    if new_email:
        email_changed.send(current_app._get_current_object(), user=user)

    # you should notify user that a confirmation email has been sent
    # for the user to confirm their email address
    return jsonify_status_code(201, id=user.id)

@subscriptions.route('/plan/', methods=['POST'])
@process_form(ChangePlanForm)
@requires_user
def change_plan():
    """Change the plans of user.
    """
    user = g.user
    data = g.form_data

    # TODO: use the name on the credit card if user.name is None

    #if not user.email:
    #    raise abort(401, 'You need to fill out your account settings first.')

    if data['plan']:
        stripe_plan = User.PLANS[data['plan']]['stripe']
    else:
        stripe_plan = None

    stripe_sync(user, stripe_plan=stripe_plan, plan=data['plan'],
                token=data.get('stripeToken'))
    user.save()

    return jsonify_status_code(201, id=user.id)

@subscriptions.route('/', methods=['PATCH'])
@process_form(ModifyUserForm)
@requires_user
def modify_user():
    """Call when user requests changes to their account settings. Not for
    changing plans. Use the change_plan route for that.
    """
    user = g.user
    data = g.form_data

    if data['current_password']:
        # check if current_password matches
        if not user.check_password(data['current_password']):
            raise abort(401, 'Password was incorrect', field='current_password')

        if data['new_password']:
            # set the new password
            user.set_password(data['new_password'])

    elif data['new_password']:
        raise abort(401, 'Password was incorrect', field='new_password')

    if 'email' in g.raw_data:
        if data['email'] == '':
            user.email = None
            new_email = False
        else:
            new_email = not data['email'] == user.email
            # check if requested email change is already used by another user
            # TODO: could catch error when updating db with a unique constraint
            # on email
            if new_email and \
               User.select().where((User.email == data['email']) & \
                                   (User.platform == user.platform)).count() > 0:
                raise abort(400, 'That email is already taken', field='email')

            user.email = data['email']
    else:
        new_email = False

    if data['name']:
        user.name = data['name']

    # TODO: fix this (checkbox inputs don't send false by default)
    if not g.raw_data.get('notifications') is None:
        user.notifications = not g.raw_data['notifications'] == 'false'

    if new_email:
        user.email_confirmed = False

    #stripe_sync(user, data['plan'], data['stripeToken'])
    # update user record
    user.save()

    #if data['plan']:
    #    change_plan()

    if new_email:
        email_changed.send(current_app._get_current_object(), user=user)

    # you should notify user that a confirmation email has been sent if
    # user changed email addresses
    return jsonify_status_code(201, id=user.id)

@subscriptions.route('/', methods=['DELETE'])
@requires_user
def close_account():
    """Delete the user making sure to unsubscribe to any stripe plans
    """
    user = g.user

    #if not user.subscription_id:
    #    raise abort(404, 'No subscription to delete')

    stripe_delete(user)

    # this will leave orphaned account models (ie not linked to a user)
    # remove them using the remove_orphaned method
    with db.database.transaction():
        user.logout_all()
        user.delete_instance()

    session.clear()

    return jsonify_status_code(204)

@subscriptions.route('/send-confirmation/', methods=['GET'])
@requires_user
def send_confirmation():
    """Send confirmation email to confirm address to user
    """
    if not request.is_xhr:
        raise abort(404)

    user = g.user
    email_changed.send(current_app._get_current_object(), user=user)
    return jsonify_status_code(201)

@subscriptions.route('/', methods=['GET'])
@requires_user
def settings():
    """Return the user's current settings in json format
    """
    if not request.is_xhr:
        raise abort(404)

    user = g.user
    data = user.__jsonify__()

    if request.args:
        data2 = {}
        for key in request.args.iterkeys():
            data2[key] = data[key]
        data = data2

    return jsonify(data)

@subscriptions.route('/validate/', methods=['POST', 'GET'])
def validate():
    if request.method == 'GET':
        data = request.args
    else:
        data = request.form or request.json

    logging.debug(data)

    #raise abort(401)
    #return jsonify(field='email', message='already used')
    return jsonify(status='ok')

#@subscriptions.route('/webhook/', methods=['POST'])
#def webhook():
#    # you can set this endpoint as a webhook in the stripe control panel
#    logging.debug(request.json)
#    return jsonify(status='ok')
