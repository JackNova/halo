import logging, math, time
from tweepy import TweepError

class TwitterAPIRateLimited(TweepError):
    """Gets raised if the twitter api returns a 429 response"""
    def __init__(self, reason, response, ratelimit):
        self.response = response
        self.ratelimit = ratelimit or {}
        TweepError.__init__(self, reason, response)

    @property
    def ratelimit_limit(self):
        return self.ratelimit.get('limit')
        #limit = self.response.getheader('x-rate-limit-limit')
        #return int(limit) if limit is not None else limit

    @property
    def ratelimit_reset(self):
        return self.ratelimit.get('reset')
        # reset is the unix epoch time when quota is reset
        #reset = self.response.getheader('x-rate-limit-reset')
        #return float(reset) if reset is not None else reset

    @property
    def ratelimit_remaining(self):
        return self.ratelimit.get('remaining')
        #remaining = self.response.getheader('x-rate-limit-remaining')
        #return int(remaining) if remaining is not None else remaining

    @property
    def seconds_until_reset(self):
        # TODO: test this
        val = math.ceil((float(self.ratelimit_reset) - time.time()))
        if val < 1: val = 1
        return val

    @property
    def minutes_until_reset(self):
        # TODO: test this
        val = math.ceil((float(self.ratelimit_reset) - time.time()) \
                        / 60.0)
        if val < 1: val = 1
        return val

    def __str__(self):
        status = self.response.status if self.response else \
                'unknown status'
        return 'Twitter API Rate Limited (%s) ' + \
                '[cached remaining: %s, reset: %s]: %s' % \
                (status, self.ratelimit_remaining,
                 self.ratelimit_reset, self.reason)

class TwitterAPIPreRateLimited(TwitterAPIRateLimited):
    """Gets raised if a request was not made because no quota remaining
    """
    pass

