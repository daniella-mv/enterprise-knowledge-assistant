"""External service clients.

Each adapter wraps a single external dependency behind a small interface
so callers can substitute fakes in tests without patching boto3 directly.
"""
