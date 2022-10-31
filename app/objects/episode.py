import utilities.pseudo_random_uuid as id_generator

class Episode:

    @staticmethod
    def generate_id (show_id, episode_name):
        return str(id_generator.pseudo_random_uuid("episode" + show_id + episode_name))

    def __init__(self, show_id, episode_name):
        self.id = self.generate_id(show_id, episode_name)
        self.fk_show_id = show_id
        self.episode_name = episode_name

    def to_json(self):
        return {
            'fk_show_id': self.fk_show_id,
            'episode_name': self.episode_name
        }