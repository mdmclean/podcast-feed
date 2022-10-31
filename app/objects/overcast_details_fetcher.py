import time
import urllib.request
import urllib.parse
import re
from objects.cache import Cache

class OvercastDetailsFetcher:
    def __init__(self, max_cached_items):
        self.website_cache = Cache(max_cached_items)

    def get_title_from_overcast_page(self, web_page):
        return re.search('(?<=<title>)(.*?)(?=</title>)', web_page).group(0)

    def get_overcast_page_title(self, url):
        page_title = ""
        result = self.website_cache.try_get_value(url)

        if result.is_found:
            return result.value

        web_page = urllib.request.urlopen(url).read().decode()
        time.sleep(20)
        page_title = self.get_title_from_overcast_page(web_page)
        self.website_cache.add_to_dictionary(url, page_title)
        return page_title