import logging
from peewee import *
from datetime import datetime
from app import db

# TODO: merge UserAccount settings with account

class BaseUserAccount(db.Model):
    """Use many-to-many (as opposed to one-to-many) because a user could have
    multiple devices connected to the same accounts.
    """
    user = NotImplementedError()
    account = NotImplementedError()

    # example:
    # user = ForeignKeyField(User)
    # account = ForeignKeyField(Account)

    created = DateTimeField(default=datetime.now)
    # allow user to control notifications per account
    notifications = BooleanField(default=True)
    # this field is used to deactivate an account belonging to a user if, for
    # example, they downgrade their subscription from multi to single account
    enabled = BooleanField(default=True)

    MERGE = ['notifications', 'enabled']

    def merge_with_account(self, account):
        for field in self.MERGE:
            setattr(account, field, getattr(self, field))
        return account

    @classmethod
    def from_account(cls, account_id):
        # TODO: attach enabled to users
        users = []
        account = None

        User = cls.user.rel_model
        Account = cls.account.rel_model
        UserAccount = cls

        q = UserAccount.select(UserAccount, User, Account)\
                .join(User).switch(UserAccount).join(Account)\
                .where(UserAccount.account == account_id)

        for result in q.execute():
            users.append(result.user)
            account = result.merge_with_account(result.account)

        if not account or not users:
            raise cls.DoesNotExist

        return users, account

    @classmethod
    def from_user(cls, user_id):
        # TODO: attach enabled to account
        user = None
        accounts = []

        User = cls.user.rel_model
        Account = cls.account.rel_model
        UserAccount = cls

        q = UserAccount.select(UserAccount, User, Account)\
                .join(User).switch(UserAccount).join(Account)\
                .where(UserAccount.user == user_id)

        for result in q.execute():
            accounts.append(result.merge_with_account(result.account))
            user = result.user

        # if user has no attached accounts then query won't return
        # anything
        if not user:
            user = User.get(id=user_id)

        return user, accounts

    @classmethod
    def from_user_account(cls, user_id, account_id):
        # TODO: attach enabled to account
        User = cls.user.rel_model
        Account = cls.account.rel_model
        UserAccount = cls

        try:
            result = UserAccount.select(UserAccount, User, Account)\
                    .join(User).switch(UserAccount).join(Account)\
                    .where((UserAccount.user == user_id) & \
                           (UserAccount.account == account_id)).get()

            return result.user, result.merge_with_account(result.account)
        except UserAccount.DoesNotExist:
            raise cls.DoesNotExist

    @classmethod
    def disconnect(cls, user_id, account_id):
        UserAccount = cls
        # remove the record from the many-to-many table
        # doesn't delete the account record (use a cron job for that)
        UserAccount.delete().where((UserAccount.user == user_id) & \
                                   (UserAccount.account == account_id)).execute()

    @classmethod
    def disconnect_all(cls, user_id):
        UserAccount = cls
        UserAccount.delete().where(UserAccount.user == user_id).execute()

    @classmethod
    def remove_orphaned_accounts(cls):
        tables = {
            'account': cls.account.rel_model._meta.db_table,
            'useraccount': cls._meta.db_table,
        }
        # TODO: this could be writtend using peewee
        cur = db.database.execute_sql(
            'DELETE %(account)s FROM %(account)s LEFT OUTER JOIN %(useraccount)s '
            'ON %(account)s.id=%(useraccount)s.account_id WHERE %(useraccount)s.id '
            'IS NULL' % tables)
        return cur.rowcount

    # peewee currently doesn't support composite keys so use unique constraint
    class Meta:
        indexes = (
            # create a unique on user/account
            (('user', 'account'), True),
        )
