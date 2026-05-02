import re


CACHE_SCHEMA_VERSION = "sales-v2"


def competitor_cache_key(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    return f"{CACHE_SCHEMA_VERSION}:{normalized.strip('-')}"
