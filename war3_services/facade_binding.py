"""Bind compatibility services to the existing host API, without a circular import.

No code is read, compiled or loaded from an adapter pack. The service functions
are ordinary bundled Python definitions. Sharing the explicit host namespace
preserves existing low-level API substitutions and avoids two global caches.
"""

from contextlib import contextmanager
from types import FunctionType


def _bind(function, namespace):
    if hasattr(function, "__wrapped__"):
        return contextmanager(_bind(function.__wrapped__, namespace))
    result = FunctionType(
        function.__code__,
        namespace,
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    result.__kwdefaults__ = function.__kwdefaults__
    result.__annotations__ = function.__annotations__
    result.__dict__.update(function.__dict__)
    result.__doc__ = function.__doc__
    result.__qualname__ = function.__qualname__
    return result


def bind_facades(namespace, classes):
    for cls in classes:
        for name, value in tuple(vars(cls).items()):
            if isinstance(value, (staticmethod, classmethod)):
                value = type(value)(_bind(value.__func__, namespace))
            elif isinstance(value, FunctionType):
                value = _bind(value, namespace)
            else:
                continue
            setattr(cls, name, value)
