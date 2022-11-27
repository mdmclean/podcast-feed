from google.cloud import datastore

class GoogleDatastore:

    def __init__(self):
        self.ds_client = datastore.Client()

    def store_entry(self, id, model):
        target_table = model.__class__.__name__
        string_id = str(id)
        key = self.ds_client.key(target_table, string_id)
        entity = datastore.Entity(key=key, exclude_from_indexes=("full_text",))
        entity.update(model.to_json())
        self.ds_client.put(entity)

    def check_if_entity_exists(self, key, entity_type):
        current_key = self.ds_client.get(self.ds_client.key(entity_type, key))
        return current_key is not None
    
    def get_entity_by_key(self, key, entity_type):
        entity = self.ds_client.get(self.ds_client.key(entity_type, key))
        return entity

    def get_unprocessed(self, lookup_kind, processed_column):
        query =  self.ds_client.query(kind=lookup_kind)
        query.add_filter(processed_column, "=", False)
        return list(query.fetch())
    
    def get_all(self, lookup_kind):
        query =  self.ds_client.query(kind=lookup_kind)
        return list(query.fetch())
