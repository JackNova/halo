import logging
from datetime import datetime
from peewee import *
from oset import oset
from halo.peewee_ext import JSONField, TimestampUpdatedField
from halo.loom import Weave
from app import db

#
# FIELDS
#

class UserIdsField(TextField):
    """TEXT is a bit slower than VARCHAR but it is not limited to 65535 bytes.
    It doesnt contribute to the maximum row size of 65535 bytes because it is
    stored separately
    NOTE: cant use "like" on TEXT types?
    """
    def db_value(self, value):
        return ',' + ','.join(value) + ',' if value else ''

    def python_value(self, value):
        value = value.split(',')[1:-1] if value else []
        return value

#
# MODELS
#

class Relationships(Weave, db.Model):
    # the twitter account id
    #id = PrimaryKeyField()
    id = BigIntegerField(primary_key=True)

    #created = DateTimeField(default=datetime.now)
    updated = TimestampUpdatedField(null=True)

    slackers = UserIdsField(null=True)
    buddies = UserIdsField(null=True)
    fans = UserIdsField(null=True)

    slackers_count = IntegerField(null=True)
    buddies_count = IntegerField(null=True)
    fans_count = IntegerField(null=True)

    slackers_new_index = IntegerField(default=0)
    buddies_new_index = IntegerField(default=0)
    fans_new_index = IntegerField(default=0)

    slackers_num_removed = IntegerField(default=0)
    buddies_num_removed = IntegerField(default=0)
    fans_num_removed = IntegerField(default=0)

    def num_removed(self, rel, value=None):
        if not value is None:
            setattr(self, '%s_num_removed', value)
        else:
            return getattr(self, '%s_num_removed' % rel)

    def reset_new_index(self):
        for rel in ('slackers', 'buddies', 'fans'):
            self.new_index(rel, 0)

    def new_index(self, rel, value=None):
        if not value is None:
            setattr(self, '%s_new_index' % rel, value)
        else:
            return getattr(self, '%s_new_index' % rel)

    def relationship_ids(self, rel, ids=None):
        if not ids is None:
            setattr(self, rel, ids)
            setattr(self, '%s_count' % rel, len(ids))
        else:
            return getattr(self, rel)

    def to_json(self, rpp=-1):
        """Pass None as rpp if you don't wan't any ids in result.
        """
        rels = ['slackers', 'fans', 'buddies']
        result = {}

        for field in self._meta.fields.iterkeys():
            if field in rels:
                if rpp is None:
                    continue
                if rpp == -1: rpp = None
                result[field] = getattr(self, field)[:rpp]
            else:
                result[field] = getattr(self, field)

        return result

    @classmethod
    def remove_id(cls, pk, relationship, id):
        table = cls._meta.db_table
        id = str(id)
        assert id.isdigit()
        # NOTE: there is no confirmation that id has been found and removed
        # set new_index to zero to simplify things
        q = ("UPDATE %s SET %s=REPLACE(%s,'%s,',''), " + \
                "%s_count=%s_count-1, %s_new_index=0 WHERE id=%%s") % \
                (table, relationship, relationship, id, relationship, \
                 relationship, relationship)
        db.database.execute_sql(q, (pk,))

    @classmethod
    def prepend_id(cls, pk, relationship, id):
        table = cls._meta.db_table
        id = str(id)
        assert id.isdigit()
        # NOTE: there is no confirmation row has been found and there are no
        # duplicates
        # set new_index to zero to simplify things
        q = ("UPDATE %s SET %s=CONCAT(',%s', %s), " + \
                "%s_count=%s_count+1, %s_new_index=0 WHERE id=%%s") % \
                (table, relationship, id, relationship, relationship, \
                 relationship)
        db.database.execute_sql(q, (pk,))

    @classmethod
    def move_id(cls, pk, relationship, id, position):
        """Moves id to a different location.
        """
        id = str(id)
        assert id.isdigit()
        assert isinstance(position, int)

        row = Relationships.get(id=pk)
        ids = getattr(row, relationship)
        ids.remove(id)
        ids.insert(position, id)
        # reset new index (would be hard to track new ids when moved)
        setattr(row, '%s_new_index' % relationship, 0)
        row.save()

    def change_relationship(self, user_id, old_rel, new_rel):
        # TODO: may throw a ValueError if user_id not in list
        if old_rel:
            getattr(self, old_rel).remove(user_id)
            setattr(self, '%s_new_index' % old_rel, 0)
            setattr(self, '%s_count' % old_rel, \
                    getattr(self, '%s_count' % old_rel)-1)

        if new_rel:
            getattr(self, new_rel).insert(0, user_id)
            setattr(self, '%s_new_index' % new_rel, 0)
            setattr(self, '%s_count' % new_rel, \
                    getattr(self, '%s_count' % new_rel)+1)

    def get_extended(self):
        """Returns totals, percents, and new indexes
        """
        rels = ['slackers', 'buddies', 'fans']
        results = self.to_json(rpp=None)
        total = 0

        results['relationships_updated'] = results.pop('updated')

        # calculate total
        for rel in rels:
            total += results['%s_count' % rel]

        # calculate percentages
        for rel in rels:
            if total > 0:
                ratio = results['%s_count' % rel] / float(total)
                percent = int(round(ratio * 100))
            else:
                percent = 0

            results['%s_percent' % rel] = percent

        results['relationships_total'] = total
        return results

    @classmethod
    def get_ids(cls, id, relationship, start, end):
        id = int(id)
        table = cls._meta.db_table
        sql = \
        "SELECT SUBSTRING(SUBSTRING_INDEX(%s,',',%s+1), " \
        "LENGTH(SUBSTRING_INDEX(%s,',',%s+1))+2) FROM %s WHERE id=%%s" % \
                (relationship, end, relationship, start, table)
        cur = db.database.execute_sql(sql, (id,))
        row = cur.fetchone()
        ids = row[0].split(',')

        # if end is bigger than number of ids then will return an extra blank id
        if ids and not ids[-1]:
            del ids[-1]

        return ids

    class Meta:
        db_table = 'twitter_relationships'

    #
    # LOOM
    #

    def set_loom(self, loom, save=True):
        if save:
            loom.finish(self.save)
        self.loom = loom
        return self

    def _ordered_merge(self, fresh_set, cached_list=None, new_index=0):
        """Returns list with new items prepended, and index of first old item.
        """
        if cached_list == None:
            return list(fresh_set), set(), 0

        cached_set = set(cached_list)
        if fresh_set == cached_set:
            return cached_list, set(), new_index

        new_set = fresh_set - cached_set
        old_set = cached_set - fresh_set

        if new_index:
            # adjust new_index appropriately if any ids are removed from old
            # new set
            new_index = len(set(cached_list[:new_index]) - old_set)

        results = oset(cached_list) - old_set

        # ids, old_ids, new_index
        return list(new_set) + list(results), old_set, len(new_set) + new_index

    def refresh(self, api):
        followers, friends = api.async_fetch_relationships(
            id=self.id)

        self.emit('followers', ids=followers)
        self.emit('friends', ids=friends)

        followers = set(followers)
        friends = set(friends)
        last_update = self.updated
        self.updated = datetime.now()

        for rel in ('slackers', 'fans', 'buddies'):
            if rel == 'slackers':
                ids = friends - followers
            elif rel == 'fans':
                ids = followers - friends
            else:
                ids = followers & friends

            #new_index = 0 if self.reset_new_index else self.new_index(rel)

            ids, old_ids, new_index = self._ordered_merge(
                ids, self.relationship_ids(rel), self.new_index(rel))

            # ids are not new if this is the first time fetching
            if last_update is None:
                new_index = 0

            if not self.reset_new_index:
                num_removed = self.num_removed(rel) + len(old_ids)
            else:
                num_removed = len(old_ids)

            self.num_removed(rel, num_removed)
            self.new_index(rel, new_index)
            self.relationship_ids(rel, ids)

            if self.loom:
                if rel in ['buddies', 'fans']:
                    # emit any unfollowers
                    unfollowers = old_ids - followers
                    if unfollowers:
                        self.emit('unfollowers', ids=unfollowers, relationship=rel)

                if rel in ['slackers', 'buddies']:
                    # emit any unfriends
                    unfriends = old_ids - friends
                    if unfriends:
                        self.emit('unfriends', ids=unfriends, relationship=rel)

        return self
