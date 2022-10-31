from google.cloud import datastore
import json

class GoogleDatastore:

    def __init__(self):
        self.ds_client = datastore.Client()

    def store_entry(self, id, model):
        target_table = model.__class__.__name__
        string_id = str(id)
        key = self.ds_client.key(target_table, string_id)
        entity = datastore.Entity(key=key)
        entity.update(model.to_json())
        self.ds_client.put(entity)

    def store_new_clip(self, unique_clip_id, url_base,
        start_timestamp, end_timestamp, unix_timestamp):
        
        key = self.ds_client.key('Clip', unique_clip_id)
        entity = datastore.Entity(key=key)
        entity.update({
            'overcast_url': url_base,
            'start_timestamp': start_timestamp,
            'end_timestamp': end_timestamp,
            'unix_timestamp': unix_timestamp,
        })
        self.ds_client.put(entity)

    def check_if_entity_exists(self, key, entity_type):
        current_key = self.ds_client.get(self.ds_client.key(entity_type, key))
        return current_key is not None

    def get_unprocessed(self, lookup_kind):
        query =  self.ds_client.query(kind=lookup_kind)
        # query.add_filter("processed", "=", False)
        return list(query.fetch())
