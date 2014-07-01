import logging
from peewee import *
from datetime import datetime
from halo.peewee_ext import insert_ignore, insert_update
from werkzeug.security import generate_password_hash, \
        check_password_hash
from flask_peewee.serializer import Serializer
from app import db

class BaseUser(db.Model):
    """A user represents a device or a web user. Multiple records can be linked
    together on user request to consolidate purchases/settings across devices.
    """
    #PLAN_FEATURES = NotImplementedError()

    # dictionary of service name and login modules for each service
    # override in subclasses to add supported services for logging in
    # and associating with the user record
    LOGIN_SERVICES = {}
    ADD_ACCOUNT_SERVICES = {}

    # the number of duplicate subscription_order_id allowed
    # this is used to prevent piracy but also allow user to restore
    # purchases on multiple devices
    MAX_DUPLICATE_ORDER_ID = 2

    class FeatureNotSupported(Exception): pass

    plan = NotImplementedError()
    PLANS = NotImplementedError()

    # device for the web is the id of the account used for initial login
    # if registration is done using email then device_id and device_type are
    # both null
    device_id = CharField(null=True)
    device_type = CharField(null=True) # eg. twitter, facebook, android, ios

    created = DateTimeField(default=datetime.now)

    # required to know how to send notifications to this user
    platform = CharField(choices=[
        ('Web', 'Web'),
        ('Windows8', 'Windows 8'),
        ('Android', 'Android'),
        ('iOS', 'iOS'),
    ])

    # user settings (all are optional and currently only used for web users)
    name = CharField(null=True)
    # currently no unique constraint on email just in case multiple devices
    email = CharField(null=True)
    passhash = CharField(null=True)
    email_confirmed = BooleanField(default=False)

    # override this if using multiapps
    app_id = NotImplementedError()

    # the gcm, apn, or wns id for push messaging (use email for web users)
    messaging_id = CharField(index=True, unique=True, null=True)

    # global setting for notifications (when false, disables notifications
    # for all linked accounts)
    notifications = BooleanField(default=True)

    # the stripe customer id, or the purchaseToken on Android
    #subscription_id = CharField(null=True)

    # on Android the orderId should be checked to make sure it is unique
    # might be able to get rid of this and just use subscription_id value instead
    #subscription_order_id = CharField(null=True, index=True)

    # used to calculate expiration of subscription so we can check if it's been
    # renewed
    #subscription_creation = DateTimeField(null=True)

    def set_password(self, password):
        self.passhash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.passhash, password)

    def __jsonify__(self, *extra_fields):
        """Serialize model to JSON that can be viewed by client. Used by jsonify().
        """
        safe_fields = ['name', 'email', 'platform', 'notifications',
                       'plan', 'email_confirmed'] + list(extra_fields)
        safe_fields = [field for field in safe_fields if hasattr(self, field)]
        s = Serializer()
        return s.serialize_object(self, fields={self.__class__: safe_fields})

    @classmethod
    def useraccount_model(cls):
        return cls._meta.reverse_rel['useraccount_set'].model_class

    @classmethod
    def account_model(cls):
        return cls.useraccount_model().account.rel_model

    def assert_add_account_supported(self, account_id, service):
        """Override this if you we want to support only one account per
        user or per service
        """
        assert not isinstance(self.PLANS, NotImplementedError) and \
                not isinstance(self.plan, NotImplementedError)

        # check if adding another account is supported by plan
        # FIXME: account id is not the row id
        num_accounts = self.get_num_accounts(account_id)

        plan_features = self.PLANS[self.plan]
        #return num_accounts >= plan_features['accounts']

        if num_accounts >= plan_features['accounts']:
            raise self.FeatureNotSupported(
                'Current plan doesn\'t support adding another account')

    def get_num_accounts(self, account_id=None):
        UserAccount = self.useraccount_model()

        if account_id is not None:
            return UserAccount.select()\
                    .where((UserAccount.user == self.id) & \
                           (UserAccount.account != account_id)).count()
        else:
            return UserAccount.select()\
                .where(UserAccount.user == self.id).count()


    def add_account(self, account_id, service, access_token_key,
                    access_token_secret, profile):
        self.assert_add_account_supported(account_id, service)

        UserAccount = self.useraccount_model()
        Account = self.account_model()

        # filter account data (save only fields that have a column in
        # table)
        #account_data = Account.filter_account_data(account_data)

        with db.database.transaction():
            insert_update(Account,
                          id=account_id,
                          service=service,
                          access_token_key=access_token_key,
                          access_token_secret=access_token_secret,
                          profile=profile)
            insert_ignore(UserAccount, user=self.id, account=account_id)

    def remove_account(self, account_id):
        UserAccount = self.useraccount_model()
        # remove the record from the many-to-many table
        # doesn't delete the account record (use a cron job for that)
        UserAccount.delete().where((UserAccount.user == self.id) & \
                                   (UserAccount.account == account_id)).execute()

    @classmethod
    def connect_user_account(cls, id, account_id, service,
                             access_token_key, access_token_secret, profile):
        """May throw a UserDoesNotExist or FeatureNotSupported
        exception
        """
        user = cls.select().where(cls.id == id).get()
        user.add_account(account_id, service, access_token_key,
                         access_token_secret, profile)
        return user

    @classmethod
    def login_with_account(cls, account_id, service, device_id, platform,
                           access_token_key, access_token_secret, profile,
                           messaging_id=None, app_id=None):
        """Will create a user record if it doesn't already exist
        """
        if platform == 'Web':
            # on the web the device id is the primary account id
            assert device_id is None, 'device id should be none on the web'
            device_id = account_id
            device_type = service
        else:
            device_type = platform

        try:
            user = cls.select().where((cls.device_id == device_id) & \
                                       (cls.device_type == device_type)).get()
            if messaging_id is not None:
                user.messaging_id = messaging_id

            # user may be created without app_id (for instance messaging_id registration)
            if app_id is not None and \
               not isinstance(user.app_id, NotImplementedError):
                if user.app_id is None:
                    user.app_id = app_id

        except cls.DoesNotExist:
            user = cls(device_id=device_id, device_type=device_type,
                       platform=platform, messaging_id=messaging_id)

            # add app_id if implemented on user
            if app_id is not None and \
               not isinstance(user.app_id, NotImplementedError):
                user.app_id = app_id

            user.save()

        user.add_account(account_id, service, access_token_key,
                         access_token_secret, profile)
        return user

    @classmethod
    def login_with_email(cls, email, password):
        try:
            user = cls.select().where(cls.email == email).get()
        except cls.DoesNotExist:
            raise

        if not user.check_password(password):
            raise ValueError('Password incorrect')

        return user

    @classmethod
    def disconnect_all(cls, id):
        UserAccount = cls.useraccount_model()
        UserAccount.delete().where(UserAccount.user == id).execute()

    @classmethod
    def disconnect(cls, id, account_id):
        # TODO: fix
        UserAccount = cls.useraccount_model()
        UserAccount.delete().where((UserAccount.user == id) & \
                                   (UserAccount.account == account_id)).execute()

    @classmethod
    def disconnect_service(cls, id, service):
        UserAccount = cls.useraccount_model()
        Account = cls.account_model()
        q = UserAccount.select().join(Account).where(
            (UserAccount.user == id) & (Account.service == service))\
                .execute()
        for row in q:
            row.delete_instance()

    def connected_accounts(self):
        # TODO: attach enabled to accounts
        UserAccount = self.useraccount_model()
        Account = self.account_model()
        query = Account.select().join(UserAccount).where(UserAccount.user == self.id)
        accounts = [account for account in query]
        return accounts

    def logout_all(self):
        self.disconnect_all(self.id)

    def logout(self, account_id):
        # TODO: fix
        self.disconnect(self.id, account_id)

    # peewee currently doesn't support composite keys so use unique
    # constraint
    class Meta:
        indexes = (
            # create a unique on device_id/device_type
            (('device_id', 'device_type'), True),
        )
