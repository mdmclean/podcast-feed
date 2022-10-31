import utilities.pseudo_random_uuid as id_generator

class Podcast: 
    
    def __init__(self, rss_feed_url, is_public, show_name):
        self.rss_feed_url = rss_feed_url
        self.is_public = is_public
        self.show_name = show_name
        self.id = str(id_generator.pseudo_random_uuid(rss_feed_url+show_name))

    def to_json(self):
        return {
            'rss_feed_url': self.rss_feed_url,
            'is_public': self.is_public,
            'show_name': self.show_name
        }