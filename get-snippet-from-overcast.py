from email.mime import audio
from enum import unique
import os
import subprocess
import sys
import urllib.request
import re
from mutagen.mp3 import MP3
from datetime import datetime, timedelta
from google.cloud import storage
import xml.etree.ElementTree as ET
import random
import uuid
from mutagen.easyid3 import EasyID3

PODCAST_XML_FILE = 'podcast-rss.xml'


def pseudo_random_uuid(seed):
    random.seed(seed)
    return uuid.UUID(bytes=bytes(random.getrandbits(8) for _ in range(16)), version=4)

def id3_lookup_helper(id3, tag_name):
    # add a try catch here eventually
    array_of_matches = id3[tag_name]
    if len(array_of_matches) > 0:
        return array_of_matches[0]
    else:
        return 'not found'

class Podcast:
    def __init__(self, title, publishDate, websiteLink,
        guid, displayImageLink, descriptionHtml, descriptionHtmlEncoded,
        lengthBytes, mp3Link, durationString, subtitle, podcaster,episode_title):
        self.title = title
        self.publishDate = publishDate
        self.websiteLink = websiteLink
        self.guid = guid
        self.displayImageLink = displayImageLink
        self.descriptionHtml = descriptionHtml
        self.descriptionHtmlEncoded = descriptionHtmlEncoded
        self.lengthBytes = lengthBytes
        self.mp3Link = mp3Link
        self.durationString = durationString
        self.subtitle = subtitle
        self.podcaster = podcaster
        self.episode_title = episode_title

    @classmethod
    def from_mp3(cls, formatted_mp3, overcast_url, new_tags, podcast_show_title, podcast_episode_title):
        #print(new_tags.pprint())
        #print(formatted_mp3.tags.pprint())
        #EasyID3.RegisterTextKey('artist', "TALB") # registering other places where the Podcast title may be
        #mp3_show = id3_lookup_helper(new_tags, 'artist')
        #mp3_title = id3_lookup_helper(new_tags, 'title')
        # there's mores stuff if you dig into the mp3 formatted_mp3.tags.getall('TIT2')[0].text
        current_date_string = datetime.today().strftime("%d %B, %Y")
        simple_description = 'An excerpt from ' + podcast_show_title + ' episode ' + podcast_episode_title
        podcast_title = simple_description[:50]
        return cls(podcast_title,current_date_string,overcast_url,'make a custom but deterministic guid','image_link',
            simple_description,simple_description,'length not set yet', 'mp3 link not set yet',
            'duration not set yet',simple_description,podcast_show_title,podcast_episode_title)

def parse_overcast_timestamp (timestamp):
    if(len(timestamp) == 5):
        return datetime.strptime(timestamp, "%M:%S")
    else:
        return datetime.strptime(timestamp, "%H:%M:%S")

def get_start_timestamp(end_timestamp, mins):
    end_datetime = parse_overcast_timestamp(end_timestamp)
    start_time = end_datetime - timedelta(minutes=mins)
    return start_time.strftime('%H:%M:%S')

def get_sanitized_mp3_name(text):
    trim_timesamp = re.search('^(.*[\\\/])', text).group(0)
    remove_special_characters =  re.sub('\W+', '', trim_timesamp) + ".mp3"
    return remove_special_characters

def get_title_from_overcast_page(web_page):
    return re.search('(?<=<title>)(.*?)(?=</title>)', web_page).group(0)


def pull_mp3_from_overcast(overcast_url, filename):
    web_page = urllib.request.urlopen(overcast_url).read().decode()
    mp3_link = re.search('https.*mp3', web_page).group(0)
    mp3_bytes = urllib.request.urlopen(mp3_link).read()
    mp3_file = open(filename, 'wb')
    mp3_file.write(mp3_bytes)
    return get_title_from_overcast_page(web_page)

def get_title_from_overcast(overcast_url):
    web_page = urllib.request.urlopen(overcast_url).read().decode()
    return get_title_from_overcast_page(web_page)

def get_mp3_from_overcast(overcast_url):
    storage_client = storage.Client('personalpodcastfeed')
    bucket = storage_client.bucket('podcast_feed')
    guid = pseudo_random_uuid(overcast_url)
    feed_blob = bucket.blob(PODCAST_XML_FILE)
    rss_xml_string = feed_blob.download_as_text()
    guid_string = str(guid)
    if guid_string in rss_xml_string: 
        return

    # break if rss xml string already contains guid

    full_mp3_file_name = get_sanitized_mp3_name(overcast_url)

    podcast_page_title = ''

    if not os.path.isfile(full_mp3_file_name):
        podcast_page_title = pull_mp3_from_overcast(overcast_url, full_mp3_file_name)
    else:
        podcast_page_title = get_title_from_overcast(overcast_url)
# '<title>Why AI is having an on-prem moment &mdash; The Stack Overflow Podcast &mdash; Overcast</title>'
    podcast_page_title_components = podcast_page_title.split('&mdash;', 2)
    podcast_episode_title = podcast_page_title_components[0]
    podcast_show_title = podcast_page_title_components[1]

    timestamp = re.search('([^\/]+$)', overcast_url).group(0)
    file_friendly_timestamp = timestamp.replace(':', '')
    start_minute_string = get_start_timestamp(timestamp, 2)
    end_minute_string = parse_overcast_timestamp(timestamp).strftime('%H:%M:%S')
    formatted_mp3 = MP3(full_mp3_file_name)
    podcast = Podcast.from_mp3(formatted_mp3, overcast_url, EasyID3(full_mp3_file_name), podcast_show_title, podcast_episode_title)
    unique_title = file_friendly_timestamp + re.sub('\W+', '', ((podcast.episode_title+podcast.podcaster)[:50])) + ".mp3"
    commands = ['ffmpeg', '-y', '-i', full_mp3_file_name, '-ss', start_minute_string, '-to', end_minute_string, '-c', 'copy', unique_title]
    subprocess.run(commands)
    snippet_formatted_mp3 = MP3(unique_title)
    mp3_duration_sceonds = snippet_formatted_mp3.info.length
    
    mp3_blob = bucket.blob(unique_title)
    mp3_blob.upload_from_filename(unique_title)
    podcast.mp3Link = mp3_blob.public_url
    podcast.lengthBytes = os.path.getsize(unique_title)
    podcast.durationString = "{:0>8}".format(str(timedelta(seconds=mp3_duration_sceonds)))
    podcast.guid = guid
    ET.parse
    rss = ET.fromstring(rss_xml_string)
    channel = rss.find('channel') 
    podcast_xml_subelement = ET.fromstring(create_new_podcast_entry(podcast)).find('item')
    channel.append(podcast_xml_subelement)
    with open(PODCAST_XML_FILE, 'wb') as file:
        tree = ET.ElementTree(rss)
        tree.write(file)  
    feed_blob.upload_from_filename(PODCAST_XML_FILE)

def create_new_podcast_entry(new_podcast):
    template_file = open('podcast-episode-template.xml')
    template_string = template_file.read()
    data = {'title':new_podcast.title, 
        'publishDate':new_podcast.publishDate, 
        'websiteLink':new_podcast.websiteLink,
        'guid': new_podcast.guid,
        'displayImageLink': new_podcast.displayImageLink,
        'descriptionHtml': new_podcast.descriptionHtml,
        'descriptionHtmlEncoded': new_podcast.descriptionHtmlEncoded,
        'lengthBytes': new_podcast.lengthBytes,
        'mp3Link': new_podcast.mp3Link,
        'duration': new_podcast.durationString,
        'subtitle': new_podcast.subtitle
    }
    return (template_string%data)


if __name__ == "__main__":
    argv=sys.argv[1:]
    target_podcast_link = argv[0]
    get_mp3_from_overcast(target_podcast_link)


