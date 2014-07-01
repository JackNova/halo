import logging
from datetime import datetime
from dateutil.tz import tzoffset
import pytz
from app import db

class DailyCounts(db.Model):
    MAX_LENGTH = 60
    RESET_DELTA = 8

    # your field needs to accept a list in python (e.g. JSONField)
    # you also need an additional DateTimeField called fieldname_updated

    def add_cumulative(self, utc_offset=0, **kwargs):
        return self.add_values(utc_offset, cumulative=True, **kwargs)

    def add_values(self, utc_offset=0, cumulative=False, **kwargs):
        """Pass field to be updated as a kwargs (eg. follower_count=213)
        """
        now = datetime.now()
        changed = False

        for field_name, value in kwargs.iteritems():
            updated_field_name = field_name + '_updated'
            updated = getattr(self, updated_field_name)

            if not updated:
                setattr(self, field_name, [value])
                setattr(self, updated_field_name, now)
                changed = True
                continue

            delta = self.day_delta(updated, utc_offset, now)
            values = getattr(self, field_name)

            #logging.debug('DELTA: %s, VALUE %s' % (delta, value))

            if delta <= 0:
                old_value = values[-1]

                # a new day has not occured so replace
                # latest value (or add if cumulative)
                if cumulative and not old_value is None:
                    values[-1] += value
                elif not value is None:
                    values[-1] = value

                #logging.debug('VALUES: %s' % values)

                if delta < 0:
                    # shouldn't happen
                    loagging.warning('DailyCounts delta less than zero')

                if not old_value == values[-1]:
                    changed = True
            else:
                if delta >= self.RESET_DELTA:
                    # too many days have passed since last update so
                    # reset the values
                    values[:] = [value]
                elif delta > 1:
                    # more than one day has passed since last update
                    # so we need to pad the values with nulls
                    for i in range(delta-1):
                        values.append(None)
                    values.append(value)
                else:
                    # new day so add a value
                    values.append(value)

                while len(values) > self.MAX_LENGTH:
                    # trim the values
                    del values[0]

                changed = True

            setattr(self, updated_field_name, now)

        return changed

    @classmethod
    def day_delta(cls, when, utc_offset, now=None):
        """Return days since specified time adjusted for timezone.
        A negative value indicates earlier time.
        """
        utc_offset = utc_offset or 0

        # this assumes that utc_offset accounts for DST
        local_tz = tzoffset(None, utc_offset)
        # astimezone is required or else datetime not adjusted
        when = when.replace(tzinfo=pytz.utc).\
                astimezone(local_tz)

        if now:
            # assumes now is in UTC
            now = now.replace(tzinfo=pytz.utc).\
                    astimezone(local_tz)
        else:
            now = datetime.now(local_tz)

        #logging.debug(now.date())
        #logging.debug(when.date())
        return (now.date() - when.date()).days
