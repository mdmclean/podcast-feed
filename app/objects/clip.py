from datetime import timedelta
import utilities.pseudo_random_uuid as id_generator

class Clip:

    def __init__(self, episode_id, first_timestamp, last_timestamp, is_processed):
        self.id = str(id_generator.pseudo_random_uuid("clip" + episode_id + str(first_timestamp) + str(last_timestamp)))
        self.clip_start = (first_timestamp - timedelta(minutes=2)).strftime('%H:%M:%S')
        self.clip_end = (last_timestamp + timedelta(seconds=30)).strftime('%H:%M:%S')
        self.fk_episode_id = episode_id
        self.is_processed = is_processed

    def to_json(self):
        return {
            'start_timestamp': self.clip_start,
            'end_timestamp': self.clip_end,
            'is_processed': self.is_processed,
            'fk_episode_id': self.fk_episode_id
        }