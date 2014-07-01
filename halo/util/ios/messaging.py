import logging, time
from apns import APNs, Frame, Payload
from models import User

def send_message(users, cert_file, key_file, sandbox=False, **data):
    if not isinstance(users, list):
        users = [users]

    messaging_ids = [user.messaging_id for user in users \
                        if user.messaging_id is not None]

    if not messaging_ids:
        logging.debug('No messaging ids founds')
        return

    logging.debug('Using messaging sandbox: %s' % sandbox)

    apns = APNs(
        use_sandbox=sandbox,
        cert_file=cert_file,
        key_file=key_file,
    )

    payload = Payload(**data)

    if len(users) == 1:
        logging.debug('Sending message to: %s' % messaging_ids[0])
        apns.gateway_server.send_notification(messaging_ids[0], payload)
    else:
        # Send multiple notifications in a single transmission
        frame = Frame()
        # used for reporting errors (in send_notification_multiple())
        identifier = 1
        # APNs stores notification until this time
        expiry = time.time()+3600
        # 10=send immediately, 5=send at time that conserves device power
        priority = 10
        for messaging_id in messaging_ids:
            frame.add_item(messaging_id, payload, identifier, expiry, priority)
        logging.debug('Sending message to multiple users')
        apns.gateway_server.send_notification_multiple(frame)

def remove_failed_messaging_ids(cert_file, key_file, sandbox=False):
    """Get notification errors (run this daily or weekly)
    """
    apns = APNs(
        use_sandbox=sandbox,
        cert_file=cert_file,
        key_file=key_file,
    )

    num_removed = 0

    # Get feedback messages
    for (messaging_id, fail_time) in apns.feedback_server.items():
        try:
            user = User.select().where(User.messaging_id == messaging_id).get()
            user.messaging_id = None
            user.save()
            num_removed += 1
        except User.DoesNotExist:
            pass

    return num_removed

