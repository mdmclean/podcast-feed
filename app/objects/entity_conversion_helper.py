from google.cloud import datastore
from objects.overcast_bookmark import OvercastBookmark
from objects.bookmark import Bookmark
from objects.overcast_details_fetcher import OvercastDetailsFetcher

class EntityConversionHelper:
    @staticmethod
    def bookmark_from_entity(entity:datastore.Entity):
        return Bookmark(entity["show_name"], entity["episode_name"], entity["timestamp"], entity["added_by"], entity["source"], entity["source_id"], entity["unix_time"], entity["is_processed"])

    @staticmethod
    def overcast_bookmark_from_entity(entity:datastore.Entity, fetcher:OvercastDetailsFetcher):
        full_url = entity["overcast_url"] + entity["podcast_timestamp"]
        return OvercastBookmark(full_url, entity["added_by"], entity["processed"], fetcher)