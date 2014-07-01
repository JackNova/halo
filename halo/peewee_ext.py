import logging, json
from datetime import datetime
from peewee import InsertQuery, UpdateQuery, MySQLDatabase
from peewee import Field, CharField, TextField, DateTimeField
from peewee import Node, Model, Param, Expression, OP_EQ, CommaClause

#
# DB OPERATIONS
#

class InsertIgnoreQuery(InsertQuery):
    def sql(self):
        query, params = super(InsertIgnoreQuery, self).sql()
        query = query.replace('INSERT INTO', 'INSERT IGNORE INTO')
        return (query, params)

class InsertUpdateQuery(InsertQuery):
    def __init__(self, model_class, insert=None):
        #assert isinstance(model_class._meta.database, MySQLDatabase), \
        #        'An insert update is only supported by MySQL'

        self._update = insert
        super(InsertUpdateQuery, self).__init__(model_class, insert)

    def sql(self):
        query, params = super(InsertUpdateQuery, self).sql()

        compiler = self.compiler()
        update = []
        for field, value in compiler._sorted_fields(self._update):
            if not isinstance(value, (Node, Model)):
                value = Param(value)
            update.append(Expression(field, OP_EQ, value, flat=True))

        update_query, update_params = compiler.build_query([CommaClause(*update)])
        query = '%s ON DUPLICATE KEY UPDATE %s' % (query, update_query)
        params.extend(update_params)

        return (query, params)

#    def sql(self):
#        sets, update_params = self.compiler().parse_field_dict(
#            self._update)
#        update_clause = ', '.join('%s=%s' % (f, v) for f, v in sets)
#
#        query = '%s ON DUPLICATE KEY UPDATE %s' % (query, update_clause)
#        params.extend(update_params)
#
#        return (query, params)

def execute_query(model_class, query_class, **params):
    fdict = dict((model_class._meta.fields[f], v) for f, v in params.items())
    q = query_class(model_class, fdict)
    q.execute()

def insert_ignore(model_class, **insert):
    execute_query(model_class, InsertIgnoreQuery, **insert)

def insert_update(model_class, **insert):
    """Only supported by mysql"""
    execute_query(model_class, InsertUpdateQuery, **insert)

#
# FIELDS
#

MySQLDatabase.register_fields({
    'timestamp_updated': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
})

class TimestampUpdatedField(DateTimeField):
    """Doesn't work with null=False and primary key
    """
    db_field = 'timestamp_updated'

    def db_value(self, value):
        value = datetime.now()
        return DateTimeField.db_value(self, value)

class JSONField(CharField):
    """VARCHAR fields have max length of 255 (mysql < 5.0.3) or 65,535. The
    default is 255 and can be changed by passing desired max to constructor.
    """
    def db_value(self, value):
        return value if value is None else json.dumps(value, separators=(',', ':'))

    def python_value(self, value):
        return json.loads(value) if value else value

class JSONTextField(TextField):
    """TEXT fields have a max length of 65535 characters"""
    def db_value(self, value):
        return json.dumps(value, separators=(',', ':')) if value else value

    def python_value(self, value):
        return json.loads(value) if value else value

#
# UTIL
#

def table_sql(model_class):
    return model_class._meta.database.compiler().create_table(model_class)

def enable_logging(level=logging.DEBUG):
    # TODO: test this
    logger = logging.getLogger('peewee')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)

#def log_sql(db):
#    """Log sql before it gets executed.
#    Usage in flask:
#        from app import db
#        log_sql(db.database)
#    """
#    import types
#
#    execute_sql = db.execute_sql
#
#    def _execute_sql(self, *args, **kwargs):
#        logging.warning(args)
#        logging.warning(kwargs)
#        return execute_sql(*args, **kwargs)
#
#    db.execute_sql = types.MethodType(
#        _execute_sql, db, db.__class__)
#

if __name__ == '__main__':
    # print out sql for testing
    class TestQuery(InsertUpdateQuery):
        def execute(self):
            print self.sql()

    class TestModel(Model):
        update = DateTimeField()

    execute_query(TestModel, TestQuery, update=datetime.now())

