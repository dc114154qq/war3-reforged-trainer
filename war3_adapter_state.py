"""Compatibility accessors for profile data and session-owned adapter caches."""
from war3_game_profile import current_profile


class ProfileMember:
    def __init__(self, *path):
        self.path = path

    def __get__(self, host, owner=None):
        value = current_profile().data
        for name in self.path:
            value = value[name]
        return value


class ProfileMembers:
    def __init__(self, *paths):
        self.paths = paths

    def __get__(self, host, owner=None):
        profile = current_profile()
        result = []
        for path in self.paths:
            value = profile.data
            for name in path:
                value = value[name]
            result.append(value)
        return tuple(result)


class SessionCacheField:
    """Preserve host attribute API while the session owns all live pointers."""
    def __init__(self, name):
        self.name = name

    def __get__(self, host, owner=None):
        if host is None:
            return self
        state = host.__dict__.get("_adapter_cache", host.__dict__)
        try:
            return state[self.name]
        except KeyError:
            raise AttributeError(self.name) from None

    def __set__(self, host, value):
        host.__dict__.get("_adapter_cache", host.__dict__)[self.name] = value

    def __delete__(self, host):
        state = host.__dict__.get("_adapter_cache", host.__dict__)
        try:
            del state[self.name]
        except KeyError:
            raise AttributeError(self.name) from None


def attach_adapter_cache(host, session, defaults, *, preserve=False):
    state = {}
    for name, factory in defaults.items():
        state[name] = getattr(host, name, factory()) if preserve else factory()
        host.__dict__.pop(name, None)
    session.adapter_cache = state
    session.adapter_cache_defaults = defaults
    host.__dict__["_adapter_cache"] = state
    return state
