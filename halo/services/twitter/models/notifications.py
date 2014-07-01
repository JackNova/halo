import logging
from functools import partial

class UnfollowNotifications(object):
    def __init__(self, send_function):
        self.ids = []
        self.send_function = send_function

    def set_loom(self, loom, account, users, api):
        loom.bind('unfollowers', self.refresh)
        loom.finish(partial(self.send, account, users, api))
        self.loom = loom
        return self

    def refresh(self, ids):
        self.ids.extend(ids)

    def summarize_names(self, names, max_length=60):
        """Make a list of names into a comma separated list that is truncated if
        max_length is exceeded. Will append "and others" when truncated.
        """
        phrase = names[0]

        for name in names[1:]:
            if len(phrase) + len(name) > max_length:
                phrase += ', and others'
                break
            if name is names[-1]:
                phrase += ', and ' + name
                break
            else:
                phrase += ', ' + name

        return phrase

    def send(self, account, users, api):
        #users = [user for user in users \
        #         if user.email_confirmed and user.notifications]

        if not users or not self.ids:
            return

        logging.debug('Creating unfollow notification')

        # TODO: handle errors (put this in celery task)
        try:
            unfollowers = api.lookup_users(self.ids)
        except:
            unfollowers = self.ids
            summary = None
        else:
            names = [unfollower['name'] for unfollower in unfollowers]
            summary = self.summarize_names(names)

        name = account.profile['name']

        for user in users:
            self.send_function(
                name=name,
                user=user,
                account=account,
                unfollowers=unfollowers,
                summary=summary,
            )

