import utilities.pseudo_random_uuid as id_generator

class Bookmark: 
    
    def __init__(self, show_name, episode_name, timestamp, added_by, source, source_id, bookmark_unix_time, is_processed):
        self.show_name = show_name
        self.episode_name = episode_name
        self.timestamp = timestamp
        self.added_by = added_by
        self.source = source
        self.source_id = source_id
        self.id = str(id_generator.pseudo_random_uuid(show_name+episode_name+timestamp+added_by))
        self.unix_timestamp = bookmark_unix_time
        self.is_processed = is_processed

    def to_json(self):
        return {
            'added_by': self.added_by,
            'unix_timestamp': self.unix_timestamp,
            'is_processed': self.is_processed,
            'episode_name': self.episode_name,
            'show_name': self.show_name,
            'timestamp': self.timestamp,
            'source': self.source,
            'source_id': self.source_id
        }