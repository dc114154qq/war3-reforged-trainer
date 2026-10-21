"""Tk implementation of application ports; all widget calls use the owner thread."""
from collections.abc import MutableMapping
from concurrent.futures import Future
from queue import Empty, Queue
import threading
import tkinter as tk
from types import ModuleType


class _Control:
    def __init__(self, bridge, value):
        self._bridge, self._value = bridge, value

    def __getattr__(self, name):
        value = self._bridge.invoke(lambda: getattr(self._value, name))
        if callable(value):
            return lambda *args, **kwargs: self._bridge.invoke(
                lambda: self._bridge.wrap(value(*self._bridge.unwrap(args), **self._bridge.unwrap(kwargs))))
        return self._bridge.wrap(value)

    def __call__(self, *args, **kwargs):
        return self._bridge.invoke(lambda: self._bridge.wrap(
            self._value(*self._bridge.unwrap(args), **self._bridge.unwrap(kwargs))))


class _ViewMap(MutableMapping):
    def __init__(self, bridge, values):
        self._bridge, self._values = bridge, values

    def __getitem__(self, key):
        return self._bridge.invoke(lambda: self._bridge.wrap(self._values[key]))

    def __setitem__(self, key, value):
        self._bridge.invoke(lambda: self._values.__setitem__(key, self._bridge.unwrap(value)))

    def __delitem__(self, key):
        self._bridge.invoke(lambda: self._values.__delitem__(key))

    def __iter__(self):
        return iter(self._bridge.invoke(lambda: tuple(self._values)))

    def __len__(self):
        return self._bridge.invoke(lambda: len(self._values))


class _Value(_Control):
    """UI writes publish scalar snapshots; worker reads never enter Tcl."""
    def __init__(self, bridge, value):
        super().__init__(bridge, value)
        self._lock = threading.Lock()
        self._snapshot = value.get()
        value.trace_add('write', self._changed)

    def _changed(self, *_):
        with self._lock:
            self._snapshot = self._value.get()

    def get(self):
        with self._lock:
            return self._snapshot


class TkViewPort:
    def __init__(self, root):
        self.root = root
        self.owner = threading.get_ident()
        self._values = {}
        self._calls = Queue()
        self._closed = False
        self._callbacks = set()
        self._variables = {}
        self._lifecycle = threading.Lock()
        root.bind('<Destroy>', self._destroyed, add='+')
        root.after(5, self._poll)

    def bind(self, name, value, *, callback=False):
        if threading.get_ident() != self.owner:
            raise RuntimeError('View bindings belong to the UI thread')
        if isinstance(value, dict) and name in ('id_catalog_trees', 'id_catalog_queries', 'id_catalog_statuses',
                'elephant_hotkey_checks', 'elephant_stat_values'):
            self._values[name] = _ViewMap(self, value)
        else:
            self._values[name] = _Control(self, value) if callback else self.wrap(value)
        if callback:
            self._callbacks.add(name)

    def value(self, name):
        return self._values[name]

    def validate(self, required):
        """Fail during composition when an application port has no view binding."""
        missing = set(required) - self._values.keys()
        if missing:
            raise RuntimeError('Unbound application view ports: ' + ', '.join(sorted(missing)))

    def invoke(self, action):
        if threading.get_ident() == self.owner:
            return action()
        result = Future()
        with self._lifecycle:
            if self._closed:
                raise RuntimeError('The view has closed')
            self._calls.put((action, result))
        return result.result()

    def post(self, callback, *args):
        """Queue a render callback without making a worker wait for Tk."""
        with self._lifecycle:
            if self._closed:
                raise RuntimeError('The view has closed')
            self._calls.put((lambda: callback(*args), Future()))

    def _destroyed(self, event):
        if event.widget is self.root:
            with self._lifecycle:
                self._closed = True
                while True:
                    try:
                        _, result = self._calls.get_nowait()
                    except Empty:
                        break
                    result.set_exception(RuntimeError('The view has closed'))

    def _poll(self):
        for _ in range(256):
            try:
                action, result = self._calls.get_nowait()
            except Empty:
                break
            try:
                result.set_result(action())
            except BaseException as exc:
                result.set_exception(exc)
        if not self._closed:
            self.root.after(5, self._poll)

    @staticmethod
    def _has_controls(value):
        if isinstance(value, (tk.Misc, tk.Variable)):
            return True
        if isinstance(value, dict):
            return any(TkViewPort._has_controls(v) for v in value.values())
        return False

    def wrap(self, value):
        if isinstance(value, tk.Variable):
            if id(value) not in self._variables:
                self._variables[id(value)] = _Value(self, value)
            return self._variables[id(value)]
        if (isinstance(value, tk.Misc) or
                isinstance(value, ModuleType) and value.__name__ in ('tkinter.messagebox', 'tkinter.filedialog')):
            return _Control(self, value)
        if isinstance(value, dict) and self._has_controls(value):
            return _ViewMap(self, value)
        if isinstance(value, tuple):
            return tuple(self.wrap(v) for v in value)
        if isinstance(value, list):
            return [self.wrap(v) for v in value]
        return value

    def unwrap(self, value):
        if isinstance(value, _Control):
            return value._value
        if isinstance(value, _ViewMap):
            return value._values
        if isinstance(value, tuple):
            return tuple(self.unwrap(v) for v in value)
        if isinstance(value, list):
            return [self.unwrap(v) for v in value]
        if isinstance(value, dict):
            return {k: self.unwrap(v) for k, v in value.items()}
        return value
