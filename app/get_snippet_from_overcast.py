import urllib.request
import urllib.parse
import re
import math
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
import time
from objects.bucket_manager import BucketManager
from objects.summarization_service import SummarizationService
from objects.episode_clipping_service import EpisodeClippingService
from objects.entity_conversion_helper import EntityConversionHelper
from objects.overcast_details_fetcher import OvercastDetailsFetcher
from objects.bookmark import Bookmark
from objects.overcast_bookmark import OvercastBookmark
from objects.podcast import Podcast
from objects.episode import Episode
from objects.clip import Clip
from objects.google_datastore import GoogleDatastore
from objects.app_cache import AppCache
from objects.mp3_fetcher import Mp3Fetcher
from objects.cut_and_transcribe_result import CutAndTransribeResult
import utilities.pseudo_random_uuid as id_generator

class PodcastDetails:
    def __init__(self, title, publishDate,
        guid, displayImageLink, descriptionHtml, descriptionHtmlEncoded,
        lengthBytes, mp3Link, durationString, subtitle, podcaster,episode_title):
        self.title = title
        self.publishDate = publishDate
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
    def create(cls, podcast_show_title, podcast_episode_title):
        current_date_string = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %Z")
        simple_description = 'An excerpt from ' + podcast_show_title + ' episode ' + podcast_episode_title + '.'
        podcast_title = generate_acronym(podcast_show_title) + ": "
        return cls(podcast_title,current_date_string,'make a custom but deterministic guid', '',
            simple_description,simple_description,'length not set yet', 'audio link not set yet',
            'duration not set yet',simple_description,podcast_show_title,podcast_episode_title)

def generate_acronym (text):
    common_words = ['The', 'A']
    text = " ".join(filter(lambda w: not w in common_words,text.split()))

    phrase = (text.replace('of', '')).split()
    acronym = ""
    for word in phrase:
        acronym = acronym + word[0].upper()
    return acronym

def parse_overcast_timestamp (timestamp):
    if(len(timestamp) == 5):
        return datetime.strptime(timestamp, "%M:%S")
    else:
        return datetime.strptime(timestamp, "%H:%M:%S")

def get_start_timestamp(end_timestamp, mins):
    end_datetime = parse_overcast_timestamp(end_timestamp)
    start_time = end_datetime - timedelta(minutes=mins)
    return start_time.strftime('%H:%M:%S')


def pull_mp3_from_overcast(overcast_url, filename):
    web_page = urllib.request.urlopen(overcast_url).read().decode()
    mp3_link = re.search('https.*mp3', web_page).group(0)
    mp3_bytes = urllib.request.urlopen(mp3_link).read()
    mp3_file = open(filename, 'wb')
    mp3_file.write(mp3_bytes)
    return "" 
    # TODO refactor - OvercastBookmark.get_title_from_overcast_page(None, web_page)



def store_overcast_timestamp(overcast_url, added_by, store:GoogleDatastore):
    if not(store.check_if_entity_exists(OvercastBookmark.get_identifier(overcast_url, added_by), "OvercastBookmark")):
        oc_bookmark = OvercastBookmark(overcast_url, added_by, False, None)
        store.store_entry(oc_bookmark.id, oc_bookmark)   

def get_or_add_podcast_by_name(app_cache:AppCache, store:GoogleDatastore, podcast_name:str):
    podcast_result = app_cache.podcast_cache.try_get_value(podcast_name)

    if not podcast_result.is_found:
        podcast_matches = store.find_entities_by_field("Podcast", "show_name", podcast_name)

        if not podcast_matches:
            podcast = Podcast.create("", True, podcast_name)
            store.store_entry(podcast.id, podcast)
        else:
            podcast = EntityConversionHelper.podcast_from_entity(podcast_matches[0])

        app_cache.podcast_cache.add_to_dictionary(podcast_name, podcast)
    else:
        podcast = podcast_result.value

    return podcast

def get_or_add_episode_by_name(app_cache:AppCache, store:GoogleDatastore, episode_name:str, podcast_fk:str):
    episode_result = app_cache.episode_cache.try_get_value(episode_name)
    
    if not episode_result.is_found:
        episode_matches = store.find_entities_by_field("Episode", "episode_name", episode_name)
        
        if not episode_matches:
            episode = Episode(podcast_fk, episode_name, None)
            store.store_entry(episode.id, episode)
        else:
            episode = EntityConversionHelper.episode_from_entity(episode_matches[0])

        app_cache.episode_cache.add_to_dictionary(episode_name, episode)
    else:
        episode = episode_result.value

    return episode

def convert_overcast_timestamps_to_bookmarks(overcast_web_fetcher:OvercastDetailsFetcher, store:GoogleDatastore, app_cache:AppCache ):
    unprocessed_podcast_bookmarks = store.get_unprocessed("OvercastBookmark", "processed")

    for overcast_bookmark_entity in unprocessed_podcast_bookmarks:
        overcast_bookmark = EntityConversionHelper.overcast_bookmark_from_entity(overcast_bookmark_entity, overcast_web_fetcher)

        podcast:Podcast = get_or_add_podcast_by_name(app_cache, store, overcast_bookmark.get_show_title())

        episode:Episode = get_or_add_episode_by_name(app_cache, store, overcast_bookmark.get_episode_title(), podcast.id)

        bookmark = Bookmark(episode.id, overcast_bookmark.timestamp, overcast_bookmark.added_by, "Overcast", overcast_bookmark.id, overcast_bookmark.unix_timestamp, False)
        if not store.check_if_entity_exists(bookmark.id, "Bookmark"):
            store.store_entry(bookmark.id, bookmark)

        overcast_bookmark.is_processed = True
        store.store_entry(overcast_bookmark.id, overcast_bookmark)
        

def group_unprocessed_clips(store:GoogleDatastore):
    unprocessed_bookmarks = store.get_unprocessed("Bookmark", "is_processed")

    podcasts_episodes = {}

    for bookmark_entity in unprocessed_bookmarks:
        bookmark = EntityConversionHelper.bookmark_from_entity(bookmark_entity)

        if bookmark.fk_episode_id in podcasts_episodes:
            podcasts_episodes[bookmark.fk_episode_id].append(bookmark)
        else: 
            podcasts_episodes[bookmark.fk_episode_id] = [bookmark]

    for episode in list(podcasts_episodes):
        ordered_timestamps = []

        for bookmark in podcasts_episodes[episode]:
            ordered_timestamps.append(parse_overcast_timestamp(bookmark.timestamp)) 

        ordered_timestamps.sort()   

        clustered_timestamps = []
        current_cluster = -1

        for ordered_ts in ordered_timestamps:
            if current_cluster == -1: 
                clustered_timestamps.append([])
                current_cluster = 0
                clustered_timestamps[0].append(ordered_ts)
            else:
                last_ts_in_current_group = clustered_timestamps[current_cluster][-1]
                if (ordered_ts - last_ts_in_current_group).total_seconds() < 240:
                    clustered_timestamps[current_cluster].append(ordered_ts)
                else:
                    clustered_timestamps.append([])
                    current_cluster = current_cluster + 1
                    clustered_timestamps[current_cluster].append(ordered_ts)
        
        for clips in clustered_timestamps:
            clip_bookmark_ids = episode + " ".join(str(clip) for clip in clips)
            hash = str(id_generator.pseudo_random_uuid(clip_bookmark_ids))
            current_time = time.time()
            new_clip = Clip.from_date_times(episode, clips[0], clips[-1], False, hash, len(clips), current_time, current_time)
            if not store.check_if_entity_exists(new_clip.id, "Clip"):
                store.store_entry(new_clip.id, new_clip)    
            
        for bookmark in podcasts_episodes[episode]:
            bookmark.is_processed = True
            store.store_entry(bookmark.id, bookmark)

def grab_clips(store:GoogleDatastore,  episode_clipping_service:EpisodeClippingService):
    unprocessed_clip_entities = store.get_unprocessed("Clip", "is_processed") 
    fetcher = Mp3Fetcher(20)

    for entity in unprocessed_clip_entities: 
        clip = EntityConversionHelper.clip_from_entity(entity)
        #TODO - cache
        episode_entity = store.get_entity_by_key(clip.fk_episode_id, 'Episode')
        episode = EntityConversionHelper.episode_from_entity(episode_entity)

        podcast_entity = store.get_entity_by_key(episode.fk_show_id, 'Podcast')
        podcast = EntityConversionHelper.podcast_from_entity(podcast_entity)

        if podcast.rss_feed_url is None or podcast.rss_feed_url == '':
            #wait till we know where to look!
            continue

        if not(episode.has_mp3()):
            episode.mp3_url = fetcher.get_mp3_from_rss_url(episode.episode_name, podcast.rss_feed_url)
            store.store_entry(episode.id, episode)

        if episode.has_mp3() and not(clip.has_mp3()):
            try:
                result:CutAndTransribeResult = episode_clipping_service.cut_and_transcribe_clip(episode.mp3_url, clip, False, podcast.show_name, episode.episode_name)
                clip.full_text_url = result.full_text_url
                clip.top_ngrams = result.top_ngrams
                clip.mp3_url = result.mp3_url
                clip.size_bytes = result.mp3_size_bytes
                clip.image_url = result.image_url
                clip.updated_unix_timestamp = time.time()
                clip.is_processed = True
                store.store_entry(clip.id, clip)
            except Exception as ex: 
                print ("failed for " + episode.episode_name + " - " + str(ex))


def get_number_bookmarks(clip:Clip):
    return clip.number_of_bookmarks / get_clip_length(clip)

def add_clip_summaries(store:GoogleDatastore, summarization_service:SummarizationService):
    clip_entities = store.get_all("Clip")

    clips = [EntityConversionHelper.clip_from_entity(clip) for clip in clip_entities]

    clips.sort(reverse=True, key=get_number_bookmarks)

    for clip in clips:
        if clip.reduced_text_link is None and not (clip.full_text_url is None):
            summary_result = summarization_service.get_clip_summary(clip)
            clip.topic = summary_result.topic
            # TODO - add links for reduction and summary
            store.store_entry(clip.id, clip)

def get_clip_from_id(clip_id:str, store:GoogleDatastore):
    entity = store.get_entity_by_key(clip_id, "Clip")
    return EntityConversionHelper.clip_from_entity(entity)

def redo_topic_summary_for_clip(clip_id:str, store:GoogleDatastore, summary_service:SummarizationService):
    clip = get_clip_from_id(clip_id, store)
    clip_summary = urllib.request.urlopen(clip.reduced_text_link).read().decode()
    clip.topic = summary_service.get_topic_from_text(clip_summary)
    store.store_entry(clip.id, clip)
    return clip.topic

def get_clip_length(clip:Clip):
    return math.ceil((parse_overcast_timestamp(clip.clip_end) - parse_overcast_timestamp(clip.clip_start)).total_seconds() / 60)

def get_top_clips(store:GoogleDatastore):
    clip_entities = store.get_all("Clip")

    clips = [EntityConversionHelper.clip_from_entity(clip) for clip in clip_entities]

    clips.sort(reverse=True, key=get_number_bookmarks)
    
    yield "<style type='text/css'>.myTable { background-color:#eee;border-collapse:collapse; }.myTable th { background-color:#000;color:white;width:50%;position: sticky; }.myTable td, .myTable th { padding:5px;border:1px solid #000; }</style>"
    yield "<table class='myTable'><th>Id</th><th>Number of bookmarks</th><th>Podcast</th><th>Episode</th><th>Start Time</th><th>Length</th><th>Episode Link</th><th>Clip Link</th><th>ngram</th><th>Full text link</th><th>Reduced text</th><th>Summary text</th><th>Topic</th>"

    for clip in clips:
        episode_entity = store.get_entity_by_key(clip.fk_episode_id, 'Episode')
        episode = EntityConversionHelper.episode_from_entity(episode_entity)

        podcast_entity = store.get_entity_by_key(episode.fk_show_id, 'Podcast')
        podcast = EntityConversionHelper.podcast_from_entity(podcast_entity)

        clip_start_seconds = 0
        start_timestamp_parts = clip.clip_start.split(":")
        if len(start_timestamp_parts) == 3:
            clip_start_seconds = 3600*int(start_timestamp_parts[0]) + 60*int(start_timestamp_parts[1]) + int(start_timestamp_parts[2])
        else:
            clip_start_seconds = + 60*int(start_timestamp_parts[0]) + int(start_timestamp_parts[1])

        minutes_to_listen_to = get_clip_length(clip)

        yield "<tr>"
        yield "<td>" + str(clip.id) + "</td>"
        yield "<td>" + str(clip.number_of_bookmarks) + "</td>"
        yield "<td>" + podcast.show_name + "</td>"
        yield "<td>" + episode.episode_name + "</td>"
        yield "<td>" + str(clip.clip_start) + "</td>"
        yield "<td>" + str(minutes_to_listen_to) +" minutes</td>"
        if episode.mp3_url is not None and episode.mp3_url != 'not found in RSS feed':
            yield "<td><a href='"+ str(episode.mp3_url) + "#t=" + str(clip_start_seconds) + "'>link</a></td>"
        else:
            yield "<td>no link</td>"
        if clip.mp3_url is not None:
            yield "<td><a href='"+ str(clip.mp3_url) + "' target='_blank'>link</a></td>"
        else:
            yield "<td>no link</td>"
        yield "<td>" + str(clip.top_ngrams) + "</td>"
        if clip.full_text_url is not None:
            yield "<td><a href='"+ str(clip.full_text_url) + "'' target='_blank'>link</a></td>"
        else:
            yield "<td>no link</td>"
        if clip.reduced_text_link is not None:
            yield "<td><a href='"+ str(clip.reduced_text_link) + "' ' target='_blank'>link</a></td>"
        else:
            yield "<td>no link</td>"
        if clip.summary_text_link is not None:
            yield "<td><a href='"+ str(clip.summary_text_link) + "' ' target='_blank'>link</a></td>"
        else:
            yield "<td>no link</td>"
        if clip.topic is not None:
            yield "<td>"+ str(clip.topic) + "</td>"
        else:
            yield "<td></td>"
        yield "</tr> "

    yield "</ul>"


# assumes that the feed xml is already created and stored in local directory
# TODO - create a new feed from scratch if it doesn't exist
def create_new_podcast_feed(feed_file_name:str, bucket_manager:BucketManager):
    feed_blob = bucket_manager.get_blob(feed_file_name)
    if not feed_blob.exists():
        feed_blob.upload_from_filename(feed_file_name)

def add_clip_to_feed(feed_name:str, clip_id:str, bucket_manager:BucketManager, store:GoogleDatastore):
    feed_blob = bucket_manager.get_blob(feed_name)
    if not feed_blob.exists():
        raise Exception("Feed file does not exist")

    rss_xml_string = feed_blob.download_as_text()

    clip:Clip = get_clip_from_id(clip_id, store)
    episode:Episode = get_episode_from_id(clip.fk_episode_id, store)
    podcast:Podcast = get_podcast_from_id(episode.fk_show_id, store)

    guid_string = str(clip.id)

    if guid_string in rss_xml_string: 
        return ""    # break if rss xml string already contains guid

    mp3_duration_seconds = math.ceil((parse_overcast_timestamp(clip.clip_end) - parse_overcast_timestamp(clip.clip_start)).total_seconds())

    podcast = PodcastDetails.create(podcast.show_name, episode.episode_name)
    podcast.lengthBytes = clip.size_bytes
    podcast.durationString = "{:0>8}".format(str(timedelta(seconds=mp3_duration_seconds)))
    podcast.guid = clip.id
    text_for_audio = urllib.request.urlopen(clip.summary_text_link).read().decode()
    podcast.descriptionHtml = podcast.descriptionHtml + "<br/>" + "<br/>" + text_for_audio
    podcast.mp3Link = clip.mp3_url
    podcast.title = clip.topic
    podcast.displayImageLink = clip.image_url
    
    print ("Adding to podcast feed...")
    rss = ET.fromstring(rss_xml_string)
    channel = rss.find('channel') 
    podcast_entry_string = create_new_podcast_entry(podcast)
    podcast_xml_subelement = ET.fromstring(podcast_entry_string).find('item')
    channel.append(podcast_xml_subelement)
    with open(feed_name, 'wb') as file:
        tree = ET.ElementTree(rss)
        tree.write(file)

    feed_blob.upload_from_filename(feed_name)

def clean_up_episode_names (store:GoogleDatastore):
    episode_entries = store.get_all("Episode")

    episodes = [EntityConversionHelper.episode_from_entity(ep) for ep in episode_entries]

    for ep in episodes: 
        ep.episode_name = ep.episode_name.replace("&rsquo;", "'")
        store.store_entry(ep.id, ep)

def create_new_podcast_entry(new_podcast):
    template_file = open('podcast-episode-template.xml')
    template_string = template_file.read()
    data = {'title':new_podcast.title, 
        'publishDate':new_podcast.publishDate, 
        'websiteLink':new_podcast.mp3Link,
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

def get_episode_from_id(episode_id:str, store:GoogleDatastore):
    episode_entity = store.get_entity_by_key(episode_id, "Episode")
    episode = EntityConversionHelper.episode_from_entity(episode_entity)
    return episode

def get_podcast_from_id(podcast_id:str, store:GoogleDatastore):
    podcast_entity = store.get_entity_by_key(podcast_id, "Podcast")
    podcast = EntityConversionHelper.podcast_from_entity(podcast_entity)
    return podcast

def reprocess_clip_audio(clip_id:str, store:GoogleDatastore, episode_clipping_service):
    clip:Clip = get_clip_from_id(clip_id, store)
    episode:Episode = get_episode_from_id(clip.fk_episode_id, store)
    podcast:Podcast = get_podcast_from_id(episode.fk_show_id, store)
    episode_clipping_service.cut_and_transcribe_clip(episode.mp3_url, clip, False, podcast.show_name, episode.episode_name)