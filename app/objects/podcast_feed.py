import uuid

class PodcastFeed: 
    
    def __init__(self, rss_feed_url, is_public, show_name):
        self.rss_feed_url = rss_feed_url
        self.is_public = is_public
        self.show_name = show_name
        self.id = uuid.uuid4()

    def to_json(self):
        return {
            'rss_feed_url': self.rss_feed_url,
            'is_public': self.is_public,
            'show_name': self.show_name
        }