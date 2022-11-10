from datetime import timedelta
import utilities.pseudo_random_uuid as id_generator

class Clip:

    def __init__(self, id, episode_id, clip_start, clip_end, is_processed, bookmark_hash, number_of_bookmarks):
        self.fk_episode_id = episode_id
        self.is_processed = is_processed
        self.bookmark_hash = bookmark_hash
        self.number_of_bookmarks = number_of_bookmarks
        self.id = id
        self.clip_start = clip_start
        self.clip_end = clip_end
    
    @classmethod
    def from_date_times(cls, episode_id, first_timestamp, last_timestamp, is_processed, bookmark_hash, number_of_bookmarks):
        clip_start = (first_timestamp - timedelta(minutes=2)).strftime('%H:%M:%S')
        clip_end = (last_timestamp + timedelta(seconds=30)).strftime('%H:%M:%S')    
        id = str(id_generator.pseudo_random_uuid("clip" + episode_id + str(first_timestamp) + str(last_timestamp)))   
        return cls(id, episode_id, clip_start, clip_end, is_processed, bookmark_hash, number_of_bookmarks)

    def to_json(self):
        return {
            'start_timestamp': self.clip_start,
            'end_timestamp': self.clip_end,
            'is_processed': self.is_processed,
            'fk_episode_id': self.fk_episode_id,
            'bookmark_hash': self.bookmark_hash,
            'number_of_bookmarks': self.number_of_bookmarks
        }