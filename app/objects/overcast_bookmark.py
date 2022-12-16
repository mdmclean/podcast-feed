import time
from objects.overcast_details_fetcher import OvercastDetailsFetcher
import utilities.pseudo_random_uuid as id_generator
import re

class OvercastBookmark:

    @staticmethod
    def get_identifier(overcast_url, added_by):
        return str(id_generator.pseudo_random_uuid(overcast_url+added_by))

    # TODO update this default constructor to receive all properties and add new creation logic wrapper
    def __init__(self, overcast_url, added_by, is_processed, fetcher:OvercastDetailsFetcher):
        self.overcast_url = overcast_url
        self.added_by = added_by
        self.id = OvercastBookmark.get_identifier(overcast_url, added_by)
        self.is_processed = is_processed
        self.timestamp = re.search(r'([^\/]+$)', overcast_url).group(0) #TODO - bug if a timestamp isn't provided
        self.overcast_url_base = re.search(r'^(.*[\/])', overcast_url).group(0)
        self.unix_timestamp = time.time()
        self.show_title = None
        self.episode_title = None
        self.fetcher = fetcher

    def load_podcast_details(self):
        page_title = self.fetcher.get_overcast_page_title(self.overcast_url_base)
        podcast_page_title_components = page_title.split('&mdash;', 2)
        self.episode_title = podcast_page_title_components[0].strip().replace('&ndash;', '-')
        if len(podcast_page_title_components) > 1:
            self.show_title = podcast_page_title_components[1].strip()
        else:
            self.show_title = 'no title'

    def get_show_title(self):
        if self.show_title is not None:
            return self.show_title
        else:
            self.load_podcast_details()
            return self.show_title
    
    def get_episode_title(self):
        if self.show_title is not None:
            return self.episode_title
        else:
            self.load_podcast_details()
            return self.episode_title

    def to_json(self):
        return {
            'overcast_url': self.overcast_url_base,
            'podcast_timestamp': self.timestamp,
            'added_by': self.added_by,
            'unix_timestamp': self.unix_timestamp,
            'processed': self.is_processed
        }