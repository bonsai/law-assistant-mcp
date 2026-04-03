# -*- coding: utf-8 -*-
import time

class Cache:
    def __init__(self):
        self._store = {}

    def set(self, key, value, ttl_seconds):
        self._store[key] = (value, time.time() + ttl_seconds)

    def get(self, key):
        entry = self._store.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def clear(self):
        self._store.clear()

cache = Cache()

TTL_SEARCH   = 30 * 60
TTL_LAW      = 24 * 60 * 60
TTL_REVISION = 60 * 60
