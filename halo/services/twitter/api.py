import math, time, urllib, json, logging
from flask import current_app
from tweepy import OAuthHandler, API, TweepError, Cursor
from tweepy.parsers import JSONParser
from errors import TwitterAPIRateLimited, TwitterAPIPreRateLimited

try:
    import gevent
except ImportError:
    pass

class TweepyProxy(object):
    """We can't just override tweepy's API because the method that
    makes the request is inside of an inner class. Will check twitter
    rate limit status before making a request.
    """
    def __init__(self, account, rate_limit_buffer=1, **kwargs):

        auth = OAuthHandler(
            current_app.config['TWITTER_CONSUMER_KEY'],
            current_app.config['TWITTER_CONSUMER_SECRET'])

        auth.set_access_token(account.access_token_key,
                              account.access_token_secret)

        self.rate_limit_buffer = rate_limit_buffer
        kwargs['parser'] = JSONParser()
        kwargs['api_root'] = '/1.1'
        self.api = API(auth, **kwargs)
        self.rate_limits = {}

    def finish(self, account, save=False):
        self.save_rate_limits(account)

        if save:
            account.save()

    #
    # RATE LIMIT METHODS
    #

    def update_rate_limits(self, endpoint):
        if getattr(self.api, 'last_response', None):
            self.rate_limits[endpoint] = {
                'limit': self.ratelimit_limit,
                'remaining': self.ratelimit_remaining,
                'reset': self.ratelimit_reset,
            }

    def load_rate_limits(self, account):
        rate_limits = account.rate_limits
        self.rate_limits.update(rate_limits)

    def save_rate_limits(self, account):
        account.rate_limits = self.rate_limits

    def set_rate_limits(self, rate_limits):
        self.rate_limits.update(rate_limits)

    @property
    def ratelimit_limit(self):
        limit = self.api.last_response.getheader('x-rate-limit-limit')
        return int(limit) if limit is not None else limit

    @property
    def ratelimit_reset(self):
        reset = self.api.last_response.getheader('x-rate-limit-reset')
        return float(reset) if reset is not None else reset

    @property
    def ratelimit_remaining(self):
        remaining = self.api.last_response.getheader(
            'x-rate-limit-remaining')
        return int(remaining) if remaining is not None else remaining

    #
    # PROXY METHODS
    #

    def __getattr__(self, name):
        attr = getattr(self.api, name)
        if not callable(attr): return attr

        def func(*args, **kwargs):
            # FIXME: assumes we're doing an authenticated rate
            # limited call
            # some aren't (like unfollowing)
            #logging.warning(name)
            #logging.warning(self.rate_limits)

            if name in self.rate_limits:
                ratelimit = self.rate_limits[name]

                # the twitter api is misreporting the rate limits of
                # 'me' endpoint as 180 when it seems to be 15
                if name == 'me' and ratelimit['remaining'] >= 165:
                    logging.debug('adjusting rate limit for the ' + \
                                  '"me" endpoint')
                    ratelimit['remaining'] -= 165

                #print ratelimit['remaining']
                #print ratelimit['reset']
                #print time.time()

                if ratelimit['remaining'] <= self.rate_limit_buffer and \
                   ratelimit['reset'] > time.time():
                    if hasattr(self.api, 'last_response'):
                        last_response = self.api.last_response
                    else:
                        last_response = None
                    raise TwitterAPIPreRateLimited(
                        'No quota left', last_response, ratelimit)

            try:
                result = attr(*args, **kwargs)
            except TweepError, e:
                self.update_rate_limits(name)
                self.handle_error(e, name)
            else:
                self.update_rate_limits(name)

            return result

        return func

    def handle_error(self, e, name):
        if e.response:
            if e.response and e.response.status == 429:
                content = e.response.read()
                #message = json.loads(content)['errors'][0]['message']
                raise TwitterAPIRateLimited(
                    content, e.response, self.rate_limits.get(name))
        raise

    #
    # UTIL METHODS
    #

    @classmethod
    def trim_users(cls, users):
        """Remove fields we don't use client side to save bandwidth"""
        if isinstance(users, list):
            for i, user in enumerate(users):
                users[i] = cls.trim_users(user)
        else:
            fields = set([
                'name',
                'location',
                'profile_image_url',
                'created_at',
                'url',
                'id',
                'protected',
                'followers_count',
                'lang',
                'verified',
                'description',
                'friends_count',
                'statuses_count',
                'screen_name',
                'following',
                'status',
            ])
            users = dict((key, users.get(key)) for key in fields)

        return users

    #
    # ADDITIONAL API METHODS
    #

    def ordered_lookup_users(self, ids):
        """Twitter's lookup_users endpoint may not return users in order, and may
        be missing some users, so use this instead. Currently doesn't accept
        screen names, only numeric twitter ids.
        """
        id_key = 'id' if ids and isinstance(ids[0], int) else 'id_str'
        users = dict((user[id_key], user) for user in self.lookup_users(ids))
        return [users.get(id, {'id': None}) for id in ids]

    def fetch_all(self, relationship, state=None, **kwargs):
        method = getattr(self, '%s_ids' % relationship)

        if state is None:
            state = {'ids': [], 'cursor': -1}
        else:
            state.setdefault('ids', [])
            state.setdefault('cursor', -1)

        cursor = state['cursor']

        while not cursor == 0:
            result, (prev, cursor) = method(
                cursor=cursor, stringify_ids=True, **kwargs)
            state['ids'] += result['ids']
            state['cursor'] = cursor

        return state['ids']

    def async_fetch_relationships(self, followers=None,
                                  friends=None, **kwargs):
        assert 'gevent' in globals(), 'gevent not detected'

        g1 = gevent.spawn(self.fetch_all, 'followers',
                          followers, **kwargs)
        g2 = gevent.spawn(self.fetch_all, 'friends',
                          friends, **kwargs)

        gevent.joinall([g1, g2])

        if g1.exception: raise g1.exception
        if g2.exception: raise g2.exception

        return g1.value, g2.value

# alias
Twitter = TweepyProxy
