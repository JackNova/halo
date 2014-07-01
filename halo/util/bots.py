import time, inspect
from urllib import urlencode
from datetime import timedelta
from flask import url_for, json

OUTPUT_LENGTH = 100

class Payload(object):
    def __init__(self, path):
        self.path = path

    def __call__(self, payload, loop_index, resp):
        payload = dict(payload)
        payload.update({
            'loop_index': loop_index,
            'resp': '__response__',
        })
        value = payload
        for part in self.path.split('.'):
            key = part % payload
            if key.isdigit() and isinstance(value, list):
                key = int(key)
                if 'loop_index' in part:
                    key = key % len(value)
                value = value[key]
            elif key == '__response__':
                value = resp
            else:
                value = value[key]
        return value

class Program(object):
    def __init__(self, **payload):
        self.payload = payload
        self.functions = []
        self.last_response = None
        self.last_response_status = None
        self.loop_index = 0

    def add(self, function):
        self.functions.append(function)

    def run(self):
        while True:
            for function in self.functions:
                # repeat if return True
                if function() is True:
                    self.loop_index += 1
                    break
            else:
                return

class Bot(object):
    def __init__(self, app, verbose=True, headers=None, payload=None,
                 kwargs=None, args=None):
        self.app = app
        self.verbose = verbose
        self.client = app.test_client()
        self.headers = headers or []
        self.kwargs = kwargs or {}
        self.args = args or {}
        payload = payload or {}
        self.program = Program(**payload)

    def _replace_values(self, kwargs):
        result = {}
        for key, value in kwargs.iteritems():
            if isinstance(value, Payload):
                value = value(self.program.payload, self.program.loop_index,
                              self.program.last_response)
            result[key] = str(value)
        return result

    def _prepare_request(self, endpoint, headers=None, kwargs=None,
                         args=None):
        kwargs = self._replace_values(dict(self.kwargs, **(kwargs or {})))
        args = self._replace_values(dict(self.args, **(args or {})))

        with self.app.test_request_context('/'):
            url = url_for(endpoint, **kwargs)
            if args:
                query_string = urlencode(args)
                if not '?' in url:
                    query_string = '?' + query_string
                url = url + query_string

        headers = headers or []
        headers.extend(self.headers)

        return url, headers

    def get(self, endpoint, if_last_status=None, payload_key=None, **kwargs):
        def function():
            if if_last_status is not None and \
               not self.program.last_response_status == if_last_status:
                return

            url, headers = self._prepare_request(endpoint, **kwargs)
            rv = self.client.get(url, headers=headers)
            data = json.loads(rv.data) if rv.data else dict()
            if payload_key:
                self.program.payload[payload_key] = data
            self.program.last_response = data
            self.program.last_response_status = rv.status_code

            if self.verbose:
                print 'GET: %s (%s)' % (url, rv.status)
                print ('%s' % rv.data)[:OUTPUT_LENGTH] + '...'

        self.program.add(function)
        return self

    def post(self, endpoint, if_last_status=None, payload_key=None, data=None, **kwargs):
        def function():
            if if_last_status is not None and \
               not self.program.last_response_status == if_last_status:
                return

            url, headers = self._prepare_request(endpoint, **kwargs)
            rv = self.client.post(url, headers=headers,
                                 data=self._replace_values(data))
            d = json.loads(rv.data) if rv.data else {}
            if payload_key:
                self.program.payload[payload_key] = d
            self.program.last_response = data
            self.program.last_response_status = rv.status_code

            if self.verbose:
                print 'POST: %s (%s)' % (url, rv.status)
                print ('%s' % rv.data)[:OUTPUT_LENGTH] + '...'

        self.program.add(function)
        return self

    def _prepare_payload(self, func):
        argspec = inspect.getargspec(func)
        if argspec.keywords is not None:
            return dict(self.payload)
        else:
            return dict((key, self.program.payload[key]) for key in argspec.args)

    def push(self, **kwargs):
        def function():
            self.program.payload.update(kwargs)
        self.program.add(function)
        return self

    def pop(self, **args):
        def function():
            for key in args:
                del self.program.payload[key]
        self.program.add(function)
        return self

    def call(self, *args, **kwargs):
        kw = kwargs.pop('kwargs', {})
        def function():
            for func in args:
                payload = self._prepare_payload(func)
                payload.update(kw)
                func(**payload)
            for key, func in kwargs.iteritems():
                payload = self._prepare_payload(func)
                payload.update(kw)
                result = func(**payload)
                self.program.payload.update({key: result})
        self.program.add(function)
        return self

    def split(self, **kwargs):
        def function():
            for key, new_keys in kwargs.iteritems():
                values = self.program.payload.pop(key)
                for k, v in zip(new_keys, values):
                    self.program.payload[k] = v
        self.program.add(function)
        return self

    def rename(self, key1, key2):
        def function():
            v = self.program.payload.pop(key1)
            self.program.payload[key2] = v
        self.program.add(function)
        return self

    def increment(self, **kwargs):
        def function():
            for key, value in kwargs.iteritems():
                self.program.payload[key] += value
        self.program.add(function)
        return self

    def delay(self, **kwargs):
        delay = timedelta(**kwargs)
        def function():
            time.sleep(delay.total_seconds())
        self.program.add(function)
        return self

    def repeat(self, **kwargs):
        delay = timedelta(**kwargs)
        def function():
            time.sleep(delay.total_seconds())
            return True
        self.program.add(function)
        return self

    def run(self):
        self.program.run()

    def spawn(self):
        import gevent
        # run gevent.joinall([g1, g2, ...]) to run bots
        # you should monkey patch all
        # from gevent import monkey; monkey.patch_all()
        return gevent.spawn(self.program.run)

def create_bot(app, **kwargs):
    return Bot(app, **kwargs)

if __name__ == '__main__':
    # test
    import gevent
    from gevent import monkey; monkey.patch_all()

    def double(value):
        return value * 2

    def output(value):
        print value

    g = create_bot(value=1)\
            .push(value=2)\
            .call(value=double)\
            .increment(value=1)\
            .call(output)\
            .spawn()
    gevent.joinall([g])
