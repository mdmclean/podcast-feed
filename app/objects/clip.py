from datetime import timedelta
import utilities.pseudo_random_uuid as id_generator

class Clip:

    def __init__(self, id, episode_id, clip_start, clip_end, is_processed, bookmark_hash, number_of_bookmarks, full_text_url, top_ngrams, mp3_url, image_url, size_bytes, unix_timestamp, updated_unix_timestamp, reduced_text_link, summary_text_link, topic):
        self.fk_episode_id = episode_id
        self.is_processed = is_processed
        self.bookmark_hash = bookmark_hash
        self.number_of_bookmarks = number_of_bookmarks
        self.id = id
        self.clip_start = clip_start
        self.clip_end = clip_end
        self.full_text_url = full_text_url
        self.top_ngrams = top_ngrams
        self.mp3_url = mp3_url
        self.image_url = image_url
        self.size_bytes = size_bytes
        self.unix_timestamp = unix_timestamp
        self.updated_unix_timestamp = updated_unix_timestamp
        self.reduced_text_link = reduced_text_link
        self.summary_text_link = summary_text_link
        self.topic = topic
    
    @classmethod
    def from_date_times(cls, episode_id, first_timestamp, last_timestamp, is_processed, bookmark_hash, number_of_bookmarks, unix_timestamp, updated_unix_timestamp):
        clip_start = (first_timestamp - timedelta(minutes=2)).strftime('%H:%M:%S')
        clip_end = (last_timestamp + timedelta(seconds=30)).strftime('%H:%M:%S')    
        id = str(id_generator.pseudo_random_uuid("clip" + episode_id + str(first_timestamp) + str(last_timestamp)))   
        return cls(id, episode_id, clip_start, clip_end, is_processed, bookmark_hash, number_of_bookmarks, None, None, None, None, None, unix_timestamp, updated_unix_timestamp, None, None, None)

    def to_json(self):
        return {
            'start_timestamp': self.clip_start,
            'end_timestamp': self.clip_end,
            'is_processed': self.is_processed,
            'fk_episode_id': self.fk_episode_id,
            'bookmark_hash': self.bookmark_hash,
            'number_of_bookmarks': self.number_of_bookmarks,
            'full_text_url': self.full_text_url,
            'top_ngrams': self.top_ngrams,
            'mp3_url': self.mp3_url,
            'image_url': self.image_url,
            'size_bytes': self.size_bytes,
            'unix_timestamp': self.unix_timestamp,
            'updated_unix_timestamp': self.updated_unix_timestamp,
            'reduced_text_url': self.reduced_text_link,
            'summary_text_url': self.summary_text_link,
            'topic': self.topic
        }

    def has_mp3(self):
        return self.mp3_url is not None