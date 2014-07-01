import logging
from peewee import *
from flask_peewee.serializer import Serializer
from halo.peewee_ext import JSONField
from app import db

class BaseAccount(db.Model):
    # the twitter/facebook etc.. account id
    id = BigIntegerField(primary_key=True)
    service = CharField()

    #last_fetch = DateTimeField(null=True)
    #last_view = DateTimeField(null=True)

    access_token_key = CharField()
    # some services don't use this
    access_token_secret = CharField(null=True)

    profile = JSONField(max_length=2000, default={})
    rate_limits = JSONField(max_length=2000, default={})

    def __jsonify__(self, *extra_fields):
        """Serialize model to JSON that can be viewed by client. Used by jsonify()
        """
        safe_fields = ['id', 'service',
                       'profile'] + list(extra_fields)
        safe_fields = [field for field in safe_fields if hasattr(self, field)]
        s = Serializer()
        return s.serialize_object(self, fields={self.__class__: safe_fields})

    class Meta:
        indexes = (
            # create a unique on user/account
            (('id', 'service'), True),
        )
