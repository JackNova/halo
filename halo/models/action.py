from datetime import datetime, timedelta
from blinker import Namespace
from peewee import *
from app import db

my_signals = Namespace()
failed_action = my_signals.signal('failed-action')
completed_action = my_signals.signal('completed-action')

class Meta(type):
    def __getitem__(self, arg):
        return self.registered[arg]

class ActionType(object):
    registered = {}

    __metaclass__ = Meta

    def __init__(self, value, **kwargs):
        self.value = value
        for key, value in kwargs.iteritems():
            setattr(self, key, value)
        assert not self.value in ActionType.registered
        ActionType.registered[self.value] = self

    def __eq__(self, other):
        if isinstance(other, int):
            return self.value == other
        else:
            return super(ActionType, self).__eq__(other)

    def __int__(self):
        return self.value

    def __hash__(self):
        return self.value

    def __str__(self):
        return str(self.value)

    def __unicode__(self):
        return unicode(self.value)

class BaseAction(db.Model):
    """A record of a like, follow, retweet, etc...
    """
    SKIPPED = 0 # account passed on the order
    QUEUED = 1 # like queued
    COMPLETED = 2 # successfully liked
    FAILED = 3 # like failed due to api error etc...

    created = DateTimeField(default=datetime.now, index=True)
    completed = DateTimeField(null=True, index=True)

    # TODO: replace account and user fields in subclass. eg:
    # user = ForeignKeyField(User)
    # account = ForeignKeyField(Account, index=True)
    # order = ForeignKeyField(Order)
    user = NotImplementedError()
    account = NotImplementedError()
    order = NotImplementedError()

    # If type is not used override this field
    # eg: type = NotImplementedError()
    type = IntegerField(index=True)

    # SKIPPED, QUEUED, COMPLETED, or FAILED
    status = IntegerField(index=True)
    
    def __jsonify__(self):
        return {
            'created': self.created,
            'order': self.order.id,
            'status': self.status,
            'type': self.type,
        }

    def set_completed(self, save=False):
        if not self.status == self.COMPLETED:
            self.status = self.COMPLETED
            self.completed = datetime.now()
            completed_action.send(self)
            if save:
                self.save()

    def set_failed(self, save=False):
        if not self.status == self.FAILED:
            self.status = self.FAILED
            failed_action.send(self)
            if save:
                self.save()

    @classmethod
    def expire_queued(cls, cutoff):
        """Give up on queued likes that are older than cutoff.
        """
        num_failed = 0
        q = cls.select().where((cls.created < cutoff) & \
                               (cls.status == cls.QUEUED))

        for item in q:
            item.set_failed()
            item.save()
            # TODO: fail the order?
            num_failed += 1

        return num_failed

    @classmethod
    def user_items(cls, user, rpp=20):
        return [entity for entity in cls.select().where(cls.user==user).order_by(cls.created.desc()).limit(rpp)]

    @classmethod
    def account_items(cls, account, rpp=20):
        return [entity for entity in cls.select().where(cls.account==account).order_by(cls.created.desc()).limit(rpp)]

    @classmethod
    def last_completed_item(cls, account, cutoff=None, type=None):
        """Check if there was a successful action within cutoff
        (timedelta) by account
        """
        clause = (cls.account==account) & (cls.status==cls.COMPLETED)

        if type is not None:
            clause &= (cls.type==type)

        try:
            action = cls.select().where(clause).order_by(cls.completed.desc()).get()
            if cutoff and action.completed < datetime.now() - cutoff:
                return None
        except cls.DoesNotExist:
            return None

        return action

    @classmethod
    def num_queued_items(cls, account, type=None):
        """Return the number of queued actions for an account
        """
        clause = (cls.account==account) & (cls.status==cls.QUEUED)
        if type is not None:
            clause &= (cls.type==type)

        return cls.select().where(clause).count()

    @classmethod
    def completion_rate(cls, period=timedelta(hours=4), types=None):
        """Returns the average number of likes per photo
        per second
        """
        cutoff = datetime.now() - timedelta(hours=4)
        clause = (cls.created>cutoff) & (cls.status==cls.COMPLETED)
        if types is not None:
            clause &= (cls.type<<list(types))
        item_count = cls.select().where(clause).count()
        #like_count = Like.select().where(Like.completed > cutoff).count()
        order_count = cls.select(fn.Count(fn.Distinct(cls.order))).scalar() or 1
        # num likes per order per 4 hours
        rate = item_count / float(order_count)
        # num likes per order per second
        return rate / float(4*60*60)
