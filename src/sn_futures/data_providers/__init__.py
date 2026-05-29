"""External data provider adapters.

These adapters return uniform status dictionaries and never expose full API
keys in URLs or logs.  They are intentionally thin wrappers around the shared
rate-limited cache client.
"""

