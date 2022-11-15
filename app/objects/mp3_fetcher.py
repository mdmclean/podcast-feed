import urllib.request
import urllib.parse
import re
from objects.cache import Cache
import xml.etree.ElementTree as ET

class Mp3Fetcher:
    def __init__(self, max_cached_items):
        self.rss_cache = Cache(max_cached_items)

    def get_mp3_from_rss_url(self, episode_name, rss_url):
        rss_xml_string = ""

        cache_result = self.rss_cache.try_get_value(rss_url)
        if cache_result.is_found:
            rss_xml_string = cache_result.value
        else:
            rss_xml_string = urllib.request.urlopen(rss_url).read().decode()
            self.rss_cache.add_to_dictionary(rss_url, rss_xml_string)

        rss = ET.fromstring(rss_xml_string)

        for episode in rss.iter('item'):
            print (episode.find('title').text)
            shortened_episode_name = episode_name[:50]
            episode_name_without_special_characters = re.sub('(?<=&)(.*?)(?=;)', '', shortened_episode_name)
            condensed_episode_name =  re.sub('\W+', '', (episode_name_without_special_characters))              
            if (condensed_episode_name in re.sub('\W+', '',episode.find('title').text)):
                return episode.find('enclosure').get('url')

        return 'not found in RSS feed' #TODO

    # def get_title_from_overcast_page(self, web_page):
    #     return re.search('(?<=<title>)(.*?)(?=</title>)', web_page).group(0)

    # def get_overcast_page_title(self, url):
    #     page_title = ""
    #     result = self.website_cache.try_get_value(url)

    #     if result.is_found:
    #         return result.value

    #     web_page = urllib.request.urlopen(url).read().decode()
    #     time.sleep(20)
    #     page_title = self.get_title_from_overcast_page(web_page)
    #     self.website_cache.add_to_dictionary(url, page_title)
    #     return page_title