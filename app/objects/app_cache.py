from objects.cache import Cache

class AppCache:
    def __init__(self, max_cached_items):
        self.podcast_cache = Cache(max_cached_items)
        self.episode_cache = Cache(max_cached_items)