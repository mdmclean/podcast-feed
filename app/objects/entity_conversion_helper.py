from google.cloud import datastore
from objects.overcast_bookmark import OvercastBookmark
from objects.bookmark import Bookmark
from objects.clip import Clip
from objects.episode import Episode
from objects.podcast import Podcast
from objects.overcast_details_fetcher import OvercastDetailsFetcher

class EntityConversionHelper:
    @staticmethod
    def bookmark_from_entity(entity:datastore.Entity):
        return Bookmark(entity["fk_episode_id"], entity["timestamp"], entity["added_by"], entity["source"], entity["source_id"], entity["timestamp"], entity["is_processed"])

    @staticmethod
    def overcast_bookmark_from_entity(entity:datastore.Entity, fetcher:OvercastDetailsFetcher):
        full_url = entity["overcast_url"] + entity["podcast_timestamp"]
        return OvercastBookmark(full_url, entity["added_by"], entity["processed"], fetcher)
    
    @staticmethod
    def clip_from_entity(entity:datastore.Entity):
        return Clip(entity.key, entity['fk_episode_id'], entity['start_timestamp'], entity['end_timestamp'], entity['is_processed'], entity['bookmark_hash'], entity['number_of_bookmarks'])


    @staticmethod
    def episode_from_entity(entity:datastore.Entity):
        return Episode(entity['fk_show_id'], entity['episode_name'])

    @staticmethod
    def podcast_from_entity(entity:datastore.Entity):
        return Podcast(entity['rss_feed_url'], entity['is_public'], entity['show_name'])