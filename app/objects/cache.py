class CacheResult:
    def __init__(self, is_found, value):
        self.is_found = is_found
        self.value = value

class Cache:
    def __init__(self, max_cached_items):
        self.dictionary = {}
        self.items_in_dictionary = 0
        self.tracking_list = []
        self.max_cached_items = max_cached_items

    def remove_last_item_in_tracking_list(self):
        item_to_remove = self.tracking_list.pop()
        self.dictionary.pop(item_to_remove)

    def add_to_dictionary(self, key, value):
        if self.items_in_dictionary >= self.max_cached_items:
            self.remove_last_item_in_tracking_list()
        else:
            self.items_in_dictionary = self.items_in_dictionary + 1

        self.dictionary[key] = value
        self.tracking_list.append(key)

    def move_to_front_of_tracking_list(self, key):
        self.tracking_list.append(self.tracking_list.pop(self.tracking_list.index(key)))

    def try_get_value (self, key):
        if key in self.dictionary:
            self.move_to_front_of_tracking_list(key)
            value = self.dictionary[key]
            return CacheResult(True, value)
        else:
            return CacheResult(False, None)
