import logging
from gcm import GCM
from models import User

"""
Collapse_key has to be a string

Notification_id should be set or else notification on client will overwrite previous one

It's recommended you use strings for all data values because they are converted to string by the gcm server
"""

def send_message(users, api_key, collapse_key=None, **data):
    """Will send a push message through GCM to users. If
    the registration ids are invalid then the user models will
    be updated by removal of ids. Function returns list of users
    that should be retried.
    """
    if not isinstance(users, list):
        users = [users]


    messaging_ids = [user.messaging_id for user in users \
                        if user.messaging_id is not None]

    assert len(messaging_ids) <= 1000, 'Too many users sent to GCM'

    if not messaging_ids:
        return []

    retry_users = []

    gcm = GCM(api_key)

    logging.debug('Sending GCM %s to %s' % (data, messaging_ids))
    response = gcm.json_request(
        data=data,
        registration_ids=messaging_ids,
        collapse_key=collapse_key,
    )
    logging.debug('GCM response: %s' % response)

    if 'errors' in response:
        for error, reg_ids in response['errors'].items():
            if error is 'NotRegistered':
                for reg_id in reg_ids:
                    User.update(messaging_id=None).where(
                        User.messaging_id == reg_id).execute()
            if error is 'Unavailable':
                retry_users.extend([user for user in users \
                               if user.messaging_id in reg_ids])
            else:
                logging.error('GCM Error: %s (%s)' % (error, reg_ids))

    if 'canonical' in response:
        for reg_id, canonical_id in response['canonical'].items():
            User.update(messaging_id=canonical_id).where(
                User.messaging_id == reg_id).execute()

    return retry_users
