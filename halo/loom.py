import inspect
from collections import defaultdict
from functools import partial

def getargspec(func):
    if type(func) is partial:
        args = inspect.getargspec(func.func).args
        if func.args:
            args = args[len(func.args):]
        if func.keywords and args:
            args = [arg for arg in args if not arg in func.keywords]
        return args
    else:
        return inspect.getargspec(func).args

class Loom(object):
    def __init__(self, save_data=False):
        self.funcs = defaultdict(list)
        self.data = defaultdict(list)
        self.finish_funcs = []
        self.save_data = save_data

    def bind(self, name, *funcs):
        self.funcs[name].extend(funcs)

        if name in self.data:
            for args, kwargs in self.data:
                self.call_funcs(funcs, *args, **kwargs)

        return self

    def emit(self, name, *args, **kwargs):
        if self.save_data:
            self.data[name].extend((args, kwargs))

        self.call_funcs(self.funcs[name], *args, **kwargs)

        return self

    def call_funcs(self, funcs, *args, **kwargs):
        for func in funcs:
            keys = getargspec(func)
            kwargs2 = dict((k, v) for k, v in kwargs.iteritems() if k in keys)
            func(*args, **kwargs2)

    def finish(self, *funcs):
        if funcs:
            self.finish_funcs.extend(funcs)
        else:
            self.call_funcs(self.finish_funcs)
            self.clear_data()
            self.finish_funcs = []

        return self

    def clear_data(self):
        self.data.clear()

class Weave(object):
    loom = None

    def set_loom(self, loom):
        self.loom = loom
        return self

    def emit(self, name, *args, **kwargs):
        if self.loom:
            self.loom.emit(name, *args, **kwargs)
        return self

    def bind(self, *args, **kwargs):
        self.loom.bind(*args, **kwargs)
        return self
