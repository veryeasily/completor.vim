# -*- coding: utf-8 -*-

import importlib
import os
import re
import vim

from .ident import start_column  # noqa
from .compat import integer_types, to_bytes, to_str

current = None


def _read_args(path):
    try:
        with open(path) as f:
            return [l.strip() for l in f.readlines()]
    except Exception:
        return []


class Meta(type):
    def __init__(cls, name, bases, attrs):
        if name not in ('Completor', 'Base'):
            Completor._registry[cls.filetype] = cls()

        return super(Meta, cls).__init__(name, bases, attrs)

Base = Meta('Base', (object,), {})


class Unusable(object):
    def __get__(self, inst, owner):
        raise RuntimeError('unusable')


class Completor(Base):
    _registry = {}

    filetype = Unusable()

    daemon = False
    sync = False
    trigger = None

    _type_map = {
        b'c': b'cpp'
    }

    _arg_cache = {}

    def __init__(self):
        self.input_data = ''
        self.ft = ''

    @property
    def current_directory(self):
        return vim.Function('expand')('%:p:h')

    @property
    def tempname(self):
        return vim.Function('completor#utils#tempname')()

    @property
    def filename(self):
        return vim.current.buffer.name

    @property
    def cursor(self):
        return vim.current.window.cursor

    # use cached property
    @property
    def filetype_map(self):
        m = self.get_option('completor_filetype_map') or {}
        self._type_map.update(m)
        return self._type_map

    @staticmethod
    def get_option(key):
        return vim.vars.get(key)

    @property
    def disabled(self):
        types = self.get_option('completor_disable_{}'.format(self.filetype))
        if isinstance(types, integer_types):
            return bool(types)
        if isinstance(types, (list, vim.List)):
            return to_bytes(self.ft) in types
        return False

    def match(self, input_data):
        if self.trigger is None:
            return True
        if isinstance(self.trigger, str):
            self.trigger = re.compile(self.trigger, re.X)

        return bool(self.trigger.search(input_data))

    def format_cmd(self):
        return ''

    @staticmethod
    def find_config_file(file):
        cwd = os.getcwd()
        while True:
            path = os.path.join(cwd, file)
            if os.path.exists(path):
                return path
            if os.path.dirname(cwd) == cwd:
                break
            cwd = os.path.split(cwd)[0]

    def parse_config(self, file):
        key = "{}-{}".format(self.filetype, file)
        if key not in self._arg_cache:
            path = self.find_config_file(file)
            self._arg_cache[key] = [] if path is None else _read_args(path)
        return self._arg_cache[key]

_completor = Completor()


# ft: str
def _load(ft):
    if 'common' not in _completor._registry:
        import completers.common  # noqa

    if ft not in _completor._registry:
        try:
            importlib.import_module("completers.{}".format(ft))
        except ImportError:
            return
    return _completor._registry.get(ft)


# ft: str, input_data: str
def load_completer(ft, input_data):
    if not ft or not input_data.strip():
        return

    ft = to_bytes(ft)
    ft = to_str(_completor.filetype_map.get(ft, ft))

    c = _load(ft)
    if c is None:
        omni = get('omni')
        if omni.has_omnifunc(ft):
            c = omni
    if c is None or not c.match(input_data):
        c = get('common')
    c.input_data = input_data
    c.ft = ft
    return None if c.disabled else c


def get(filetype):
    return _completor._registry.get(filetype)