import os, json, subprocess, logging
from os.path import isfile
from collections import defaultdict
import models
from models import User, Account, UserAccount
from endpoints import make_auth_token
from app import db

NotNone = object()

def reset_database():
    conn = db.database._connect(None, **db.database.connect_kwargs)
    dbname = db.database.database
    cur = conn.cursor()
    cur.execute('drop database %s; create database %s;' % (dbname, dbname))
    conn.close()

def create_tables(filename='models.py'):
    #os.system('python %s' % filename)
    subprocess.check_output('python %s' % filename, shell=True)

def _check(item, criteria):
    if criteria is None:
        return True

    if item is None:
        return False

    for key, value in criteria.iteritems():
        try:
            v = item[key]
        except TypeError:
            v = getattr(item, key)

        if value is NotNone:
            if v is None:
                return False
        elif v != value:
            return False

    return True

def get_users_account(account=None, profile=None):
    for acct in Account.select():
        if not _check(acct.profile, profile):
            continue
        if not _check(acct, account):
            continue
        break
    else:
        raise ValueError('Account not found')

    return UserAccount.from_account(acct.id)

def get_user_account(user=None, account=None, profile=None):
    users, account = get_users_account(account=account, profile=profile)

    for u in users:
        if not _check(u, user):
            continue
        break
    else:
        raise ValueError('User not found')

    return (u, account)

def get_request_info(*args, **kwargs):
    user, account = get_user_account(*args, **kwargs)
    auth_token = make_auth_token(user.id)
    headers = [
        ('Auth-Token', auth_token),
        ('Platform', user.platform),
        ('Account', str(account.id)),
        ('Service', account.service),
        #('Version', ''),
        ('User', user.device_id),
    ]
    if not isinstance(User.app_id, NotImplementedError):
        headers.append(('App-Id', user.app_id))

    return (account.service, account.id, headers)

def send_account_message(alert, body, badge=None, sound=None,
                         apportable=True, collapse_key=None,
                         **kwargs):
    from halo.util.messaging import send_message
    users = []

    users, account = get_users_account(**kwargs)

    logging.debug('Sending message to %s users' % len(users))
    return send_message(users=users, alert=alert, body=body, badge=badge,
                        sound=sound, apportable=apportable,
                        collapse_key=collapse_key)

## TODO: handle case where account has same key:value for username (but different services)
## TODO: also save the messaging_id on the User model
#
#def get_users_account(key, value):
#    for account in Account.select():
#        if account.profile[key] == value:
#            break
#    else:
#        raise ValueError('Profile not found: %s:%s' % (key, value))
#
#    users, account = UserAccount.from_account(account.id)
#    return (users, account)
#
#def get_user_account(key, value):
#    """Will find account with profile that has the key:value pair
#    """
#    users, account = get_users_account(key, value)
#    return (users[0], account)
#
#def get_auth_token(key, value):
#    """Get the auth token for an account
#    """
#    user, account = get_user_account(key, value)
#    auth_token = make_auth_token(user.id)
#    return auth_token, account.id
#
#def save_accounts(filename, fail_silently=True, **kwargs):
#    if isfile(filename):
#        with open(filename) as f:
#            data = json.loads(f.read())
#    else:
#        data = {}
#
#    for key, values in kwargs.iteritems():
#        for value in values:
#            try:
#                user, account = get_user_account(key, value)
#            except ValueError:
#                if fail_silently:
#                    continue
#                else:
#                    raise
#
#            data['%s:%s' % (key, value)] = {
#                'device_id': user.device_id,
#                'messaging_id': user.messaging_id,
#                'service': account.service,
#                'account_id': account.id,
#                'platform': user.platform,
#                'access_token_key': account.access_token_key,
#                'access_token_secret': account.access_token_secret,
#                'profile': account.profile,
#            }
#            if not isinstance(User.app_id, NotImplementedError):
#                data['%s:%s' % (key, value)]['app_id'] = user.app_id
#
#    with open(filename, 'w+') as f:
#        f.write(json.dumps(data))
#
## TODO: return account as well
#def restore_accounts(filename, **kwargs):
#    with open(filename) as f:
#        data = json.loads(f.read())
#
#    results = []
#
#    for key, values in kwargs.iteritems():
#        for value in values:
#            User.login_with_account(**data['%s:%s' % (key, value)])
#            results.append(get_user_account(key, value))
#
#    return results
#
#def send_account_message(alert, body, badge=None, sound=None, apportable=True, collapse_key=None, fail_silently=False, **kwargs):
#    from halo.util.messaging import send_message
#    users = []
#
#    for key, values in kwargs.iteritems():
#        for value in values:
#            try:
#                new_users, account = get_users_account(key, value)
#            except ValueError:
#                if fail_silently:
#                    continue
#                else:
#                    raise
#            users.extend(new_users)
#
#    logging.debug('Sending message to %s users' % len(users))
#    return send_message(users=users, alert=alert, body=body, badge=badge, sound=sound, apportable=apportable, collapse_key=collapse_key)
#
#
#def reset_test_database(filename='accounts_test.json', module=models, **kwargs):
#    save_accounts(filename, **kwargs)
#    reset_database()
#    create_tables()
#    user_accounts = restore_accounts(filename, **kwargs)
#
#    results = defaultdict(list)
#    for user, account in user_accounts:
#        results['services'].append(account.service)
#        results['account_ids'].append(account.id)
#
#        auth_token = make_auth_token(user.id)
#        results['headers'].append([('Auth-Token', auth_token)])
#        results['auth_tokens'].append(auth_token)
#
#    return results
