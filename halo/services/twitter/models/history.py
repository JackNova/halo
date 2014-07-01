import logging
from datetime import datetime
from functools import partial
from peewee import *
from app import db

class History(db.Model):
    created = DateTimeField(default=datetime.now)

    # twitter account ids
    user1 = BigIntegerField(index=True)
    user2 = BigIntegerField()

    relationship_2to1 = CharField(choices=[
        ('slackers', 'slacker'),
        ('buddies', 'buddy'),
        ('fans', 'fan'),
    ])

    @classmethod
    def items(cls, user1, start_id=-1, limit=20):
        return cls.select().where((cls.user1 == user1) & (cls.id > start_id))\
                .order_by(cls.id.desc()).limit(limit)

    class Meta:
        db_table = 'twitter_history'

    #
    # LOOM
    #

    @classmethod
    def set_loom(cls, loom, account_id):
        loom.bind('unfollowers', partial(cls.refresh, account_id))

    @classmethod
    def refresh(cls, account_id, ids, relationship):
        # TODO: bulk insert
        for unfollower in ids:
            cls.insert(
                user1=account_id,
                user2=unfollower,
                relationship_2to1=relationship).execute()

