from cachetools import TTLCache, LRUCache

# Cache configuration
CACHE_TTL = 300  # 5 minutes cache timeout
CACHE_CONFIGS = {
    'user': {
        'maxsize': 1000,
        'ttl': CACHE_TTL
    },
    'category': {
        'maxsize': 100,
        'ttl': CACHE_TTL
    },
    'settings': {
        'maxsize': 50,
        'ttl': CACHE_TTL
    },
    'links': {
        'maxsize': 500,  # LRU cache size
    }
}

# Initialize caches
USER_CACHE = TTLCache(**CACHE_CONFIGS['user'])
CATEGORY_CACHE = TTLCache(**CACHE_CONFIGS['category'])
SETTINGS_CACHE = TTLCache(**CACHE_CONFIGS['settings'])
LINKS_CACHE = LRUCache(**CACHE_CONFIGS['links'])
