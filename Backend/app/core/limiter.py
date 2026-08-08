"""
Shared rate limiter instance (slowapi / limits), used to throttle
authentication and event-ingestion endpoints. Keyed by client IP by default;
swap `key_func` for a user-id-based key once auth is resolved earlier in the
pipeline if you need per-user limits instead of per-IP.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
