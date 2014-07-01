import logging
from flask import request, abort, Blueprint, current_app
from gcm.gcm import GCMConnectionException, GCMUnavailableException
from halo.util.endpoints import jsonify_status_code
from halo.util.android.messaging import send_message as send_android_message
from halo.util.ios.messaging import send_message as send_ios_message
from blinker import Namespace
from models import User
from app import app, sentry

my_signals = Namespace()
messaging_registered = my_signals.signal('messaging-registered')

def register(platform, device_id, messaging_id, **kwargs):
    """Create user with messaging id (or update user if already exists). kwargs are extra field values for user entity on creation.
    """
    device_type = platform

    assert platform in ['iOS', 'Android']

    q = User.select().where(
        ((User.device_id == device_id) & (User.device_type == device_type)) \
         | (User.messaging_id == messaging_id))
    users = q.execute()

    user_id = None

    for user in users:
        logging.debug('Add messaging [user found]: %s' % user)
        logging.debug(user.platform)
        #assert user.platform == platform

        if not user.device_id == device_id and \
           user.device_type == device_type: #user.id == user_id:
            # In ios occurs if user reinstalled the app, upgraded the
            # os or (maybe) the app. In android the user id is the hardware
            # device id so this should never occur (would be more secure if
            # not tied to hardware)
            logging.debug('Deleting old user')
            user.delete_instance(recursive=True)

        elif not user.messaging_id == messaging_id:
            logging.debug('Updating messaging id')
            # occurs if a new messaging id is issued by apple or google
            user.messaging_id = messaging_id
            user.save()
            user_id = user.id
            messaging_registered.send(current_app._get_current_object(), user=user)

        else:
            logging.debug('Messaging id is already up to date')
            # messaging id already up to date
            user_id = user.id
            messaging_registered.send(current_app._get_current_object(), user=user)

    if not user_id:
        logging.debug('Creating user')
        # occurs when messaging id is received before first user login
        user = User(device_id=device_id, device_type=device_type,
                    messaging_id=messaging_id,
                    platform=platform,
                    **kwargs)#id = user_id
        user.save()
        user_id = user.id
        messaging_registered.send(current_app._get_current_object(), user=user)

    return user_id

def unregister(platform, device_id):
    device_type = platform

    assert platform in ['iOS', 'Android']

    # could occur if google refreshes the messaging id
    try:
        #user = User.select().where(User.id == user_id).get()
        user = User.select().where((User.device_id == device_id) & \
                                   (User.device_type == device_type)).get()
    except User.DoesNotExist:
        raise abort(404)

    user.messaging_id = None
    user.save()
    return user.id

def _combine_text(alert, body):
    if not body:
        return alert

    if alert[-1] in '.!?:;':
        separator = ' '
    else:
        separator = '. '

    return alert + separator + body

def _get_android_batches(users):
    results = {}

    for user in users:
        if 'MULTIPLE_APPS' in app.config:
            key = user.app_id
            config = app.config['MULTIPLE_APPS'][user.app_id]
        else:
            key = None
            config = app.config
        if not key in results:
            try:
                results[key] = {
                    'api_key': config['GCM_API_KEY'],
                    'users': [user],
                }
            except KeyError:
                logging.exception('Unrecognized app name')
        else:
            results[key]['users'].append(user)

    return results.values()

def _get_ios_batches(users):
    results = {}

    for user in users:
        if 'MULTIPLE_APPS' in app.config:
            key = user.app_id
            config = app.config['MULTIPLE_APPS'][user.app_id]
        else:
            key = None
            config = app.config
        if not key in results:
            try:
                results[key] = {
                    'sandbox': app.config['USE_IOS_SANDBOX'],
                    'cert_file': config['APN_CERT_FILE'],
                    'key_file': config['APN_KEY_FILE'],
                    'users': [user],
                }
            except KeyError:
                logging.exception('Unrecognized app name')
        else:
            results[key]['users'].append(user)

    return results.values()

def send_message(users, alert, body, badge=None, sound=None, apportable=True, collapse_key=None, ios_combine_text=True):
    """Platform independent function for sending push messages.
    Returns list of users that should be retried.
    NOTE: body is not displayed on iOS only android
    """

    # TODO: allow custom data

    if not isinstance(users, list):
        users = [users]

    # send android message
    android_users = [user for user in users if user.platform == 'Android' and user.messaging_id is not None]

    if len(android_users) > 1000:
        retry_users = android_users[1000:]
        android_users = android_users[:1000]
    else:
        retry_users = []

    if android_users:
        #gcm_key = app.config['GCM_API_KEY']

        data = {'alert': alert, 'body': body}

        if apportable:
            #data = {'payload': {'aps': data}}
            # currently apportable doesn't seem to support the body
            # key so combine the alert and body text
            data = {
                'payload': {
                    'aps': {'alert': _combine_text(alert, body)}
                }
            }

        for batch in _get_android_batches(android_users):
            batch.update(data)
            try:
                failed = send_android_message(
                    #users=android_users,
                    #api_key=gcm_key,
                    collapse_key=collapse_key,
                    **batch)
                retry_users.extend(failed)
            except (GCMUnavailableException, GCMConnectionException):
                logging.exception('Error sending GCM (retrying)')
                retry_users.extend(android_users)
                if sentry:
                    sentry.captureException()
            except:
                logging.exception('Error sending GCM')
                if sentry:
                    sentry.captureException()

    # send ios message
    ios_users = [user for user in users if user.platform == 'iOS' and user.messaging_id is not None]

    if ios_users:
        #use_sandbox = app.config['USE_IOS_SANDBOX']
        #cert_file = app.config['APN_CERT_FILE']
        #key_file = app.config['APN_KEY_FILE']

        # TODO: check size of payload (can't be more than 256 bytes)
        if ios_combine_text:
            text = _combine_text(alert, body)

        data = {'alert': text}
        if badge is not None:
            data['badge'] = badge
        if sound is not None:
            data['sound'] = sound

        for batch in _get_ios_batches(ios_users):
            batch.update(data)
            try:
                send_ios_message(
                    #users=ios_users,
                    #cert_file=cert_file,
                    #key_file=key_file,
                    #sandbox=use_sandbox,
                    **batch)
            except:
                logging.exception('Error sending APN')
                if sentry:
                    sentry.captureException()

    return retry_users
