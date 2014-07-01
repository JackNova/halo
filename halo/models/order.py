import logging
from datetime import datetime, timedelta
from blinker import Namespace
from flask import current_app
from peewee import *
from peewee import RawQuery
from halo.peewee_ext import JSONField
from app import db

my_signals = Namespace()
expired_order = my_signals.signal('expired-order')
failed_order = my_signals.signal('failed-order')
completed_order = my_signals.signal('completed-order')

class Meta(type):
    def __getitem__(self, arg):
        return self.registered[arg]

class OrderType(object):
    registered = {}

    __metaclass__ = Meta

    def __init__(self, value, **kwargs):
        self.value = value
        for key, value in kwargs.iteritems():
            setattr(self, key, value)
        assert not self.value in OrderType.registered
        OrderType.registered[self.value] = self

    def __eq__(self, other):
        if isinstance(other, int):
            return self.value == other
        else:
            return super(OrderType, self).__eq__(other)

    def __int__(self):
        return self.value

    def __hash__(self):
        return self.value

    def __str__(self):
        return str(self.value)

    def __unicode__(self):
        return unicode(self.value)

class BaseOrder(db.Model):
    ACTIVE = 0
    COMPLETED = 1 # num requested likes reached
    EXPIRED = 2 # num requested likes not reached before expiration
    FAILED = 3
    STOPPED = 4

    created = DateTimeField(default=datetime.now, index=True)

    # TODO: replace account and user fields in subclass. eg:
    # account = ForeignKeyField(Account)
    # user = ForeignKeyField(User)
    account = NotImplementedError()
    user = NotImplementedError()

    # type is an integer that specifies the type of action eg. retweet, follow
    # it's recommended that you use class constants for types
    # order types aren't necessarily the same as action types
    # in case an order can support more than on action type
    # If type is not used override this
    # eg: type = NotImplementedError()
    type = IntegerField(index=True)

    # the id of the item from the third-party service
    item_id = CharField(index=True)
    data = JSONField(max_length=1000)

    num_requested = IntegerField()
    num_completed = IntegerField(default=0)
    num_skipped = IntegerField(default=0)
    num_failed = IntegerField(default=0)

    # ACTIVE, COMPLETED, or FAILED
    status = IntegerField(default=ACTIVE, index=True)

    def save(self):
        if self.num_completed >= self.num_requested:
            if not self.status == self.COMPLETED:
                self.status = self.COMPLETED
                completed_order.send(self)

        super(BaseOrder, self).save()

    def __jsonify__(self):
        return {
            'created': self.created,
            'type': self.type,
            'item_id': self.item_id,
            'data': self.data,
            'num_requested': self.num_requested,
            'num_completed': self.num_completed,
            'status': self.status,
            'id': self.id,
        }

    def increment_completed(self):
        self.num_completed += 1

    def increment_skipped(self):
        self.num_skipped += 1

    def increment_failed(self, value=1):
        self.num_failed += value

    def set_failed(self, message, save=False):
        if not self.status == self.FAILED:
            self.status = self.FAILED
            failed_order.send(self, message=message)
            if save:
                self.save()

    @classmethod
    def expire_active(cls, cutoff):
        """Expire orders that haven't been finished and that are older than the cutoff.
        """
        num_expired = 0
        q = cls.select().where((cls.created < cutoff) & (cls.status == cls.ACTIVE))

        for order in q:
            order.status = cls.EXPIRED
            expired_order.send(order)
            order.save()
            num_expired += 1

        return num_expired

    @classmethod
    def account_orders(cls, account, rpp=20):
        return [entity for entity in cls.select().where(cls.account==account).order_by(cls.created.desc()).limit(rpp)]

    @classmethod
    def user_orders(cls, user, rpp=20):
        return [entity for entity in cls.select().where(cls.user==user).order_by(cls.created.desc()).limit(rpp)]

    @classmethod
    def get_next_queue_item(cls, accounts, types, action_model,
                            order_by):
        """Get the next order available to like, follow, retweet, etc...
        Returns an item that the accounts have not previously encountered,
        and that wasn't created by one of the accounts, and is one of the
        supported types.
        """
        # TODO: convert to peewee when peewee supports joins on
        # sub-selects
        # see: https://groups.google.com/forum/#!topic/peewee-orm/Lm2qYpYo88k
        # TODO: also use service
        params = {
            'action_table': action_model._meta.db_table,
            'order_table': cls._meta.db_table,
            'account_ids': ','.join(str(account.id) for account in accounts),
            'type_ids': ','.join(str(type) for type in types),
            'order_by': order_by,
        }

        # get latest order not created by account or seen by account
        sql = """
        SELECT `%(order_table)s`.* FROM `%(order_table)s` LEFT JOIN (SELECT * FROM `%(action_table)s` WHERE `%(action_table)s`.account_id IN (%(account_ids)s)) AS b ON b.order_id = `%(order_table)s`.id WHERE b.id IS NULL AND `%(order_table)s`.account_id NOT IN (%(account_ids)s) AND `%(order_table)s`.status = 0 AND `%(order_table)s`.type IN (%(type_ids)s) ORDER BY %(order_by)s LIMIT 1
        """ % params
        logging.debug(sql)

        rq = RawQuery(cls, sql)

        orders = [order for order in rq.execute()]

        if not orders:
            raise cls.DoesNotExist()
        return orders[0]

    @classmethod
    def get_next_chronological(cls, accounts, types, action_model,
                               sort_order='DESC'):
        """Returns the next available order in order of created field.
        """
        order_by = '`%s`.created %s' % (cls._meta.db_table, sort_order)
        return cls.get_next_queue_item(accounts,types, action_model,
                                       order_by, sort_order)

    @classmethod
    def get_next(cls, account):
        """Get an order for an account to like, follow, retweet, etc..
        """
        raise NotImplementedError()
