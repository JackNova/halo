import logging
from datetime import datetime
from functools import partial
from peewee import *
from flask_peewee.serializer import Serializer
from halo.peewee_ext import JSONField, TimestampUpdatedField
from halo.services.models import DailyCounts
from app import db

class RelationshipStats(DailyCounts):
    id = BigIntegerField(primary_key=True)

    MAX_LENGTH = 60 # keep stats up to 60 days
    # fields required for DailyCounts
    followers = JSONField(max_length=800, default=[])
    friends = JSONField(max_length=800, default=[])
    #unfollows = JSONField(max_length=500, default=[])
    unfollowers = JSONField(max_length=800, default=[])
    unfriends = JSONField(max_length=800, default=[])
    followers_updated = DateTimeField()
    friends_updated = DateTimeField()
    #unfollows_updated = DateTimeField()
    unfollowers_updated = DateTimeField()
    unfriends_updated = DateTimeField()

    class Meta:
        db_table = 'twitter_relationshipstats'

    #
    # LOOM
    #

    def set_loom(self, loom, utc_offset=None):
        for rel in ('followers', 'friends', 'unfollowers', 'unfriends'):
            loom.bind(rel, partial(self.refresh, rel, utc_offset=utc_offset))
        self.loom = loom
        return self

    def refresh(self, key, ids, utc_offset=None):
        if key in ('friends', 'followers'):
            self.add_values(utc_offset, **{key: len(ids)})
        else:
            self.add_cumulative(utc_offset, **{key: len(ids)})
        return self
