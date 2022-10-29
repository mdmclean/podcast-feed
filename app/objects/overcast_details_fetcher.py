import urllib.request
import urllib.parse
import re

class OvercastDetailsFetcher:
    def __init__(self):
        self.overcast_page_dictionary = {}

    def get_title_from_overcast_page(self, web_page):
        return re.search('(?<=<title>)(.*?)(?=</title>)', web_page).group(0)

    def get_overcast_page_title(self, url):
        if url in self.overcast_page_dictionary:
            return self.overcast_page_dictionary[url]

        web_page = urllib.request.urlopen(url).read().decode()
        page_title = self.get_title_from_overcast_page(web_page)
        self.overcast_page_dictionary[url] = page_title
        return page_title