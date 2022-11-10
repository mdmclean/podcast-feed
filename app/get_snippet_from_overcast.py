import os
import subprocess
import sys
import urllib.request
import urllib.parse
import re
from datetime import datetime, timedelta, timezone
from google.cloud import storage
import xml.etree.ElementTree as ET
from google.cloud import speech_v1p1beta1 as speech
from numpy import true_divide
import yake
from mutagen.id3 import APIC, ID3
from google.cloud import texttospeech
from google.cloud import datastore
import time
from objects.entity_conversion_helper import EntityConversionHelper
from objects.overcast_details_fetcher import OvercastDetailsFetcher
from objects.bookmark import Bookmark
from objects.overcast_bookmark import OvercastBookmark
from utilities.pseudo_random_uuid import pseudo_random_uuid
from objects.podcast import Podcast
from objects.episode import Episode
from objects.clip import Clip
from objects.google_datastore import GoogleDatastore
from objects.app_cache import AppCache
import utilities.pseudo_random_uuid as id_generator

PODCAST_XML_FILE = 'podcast-rss.xml'

def speech_to_text(clip_gs_link, channel_count):
    diarization_config = speech.SpeakerDiarizationConfig(
        enable_speaker_diarization=True,
        min_speaker_count=1,
        max_speaker_count=2,
    )

    config = speech.RecognitionConfig()
    config.language_code = "en-us" 
    config.encoding = speech.RecognitionConfig.AudioEncoding.FLAC
    config.enable_automatic_punctuation = True
    config.audio_channel_count = channel_count

    audio = speech.RecognitionAudio()
    audio.uri = clip_gs_link

    text = speech_to_text_google(config, audio)
    return text 

def get_top_keywords (text):
    language = "en"
    max_ngram_size = 3
    deduplication_threshold = 0.1
    deduplication_algo = 'seqm'
    windowSize = 1
    numOfKeywords = 5
    kw_extractor = yake.KeywordExtractor(lan=language, n=max_ngram_size, dedupLim=deduplication_threshold, dedupFunc=deduplication_algo, windowsSize=windowSize, top=numOfKeywords, features=None)
    keywords = kw_extractor.extract_keywords(text)
    keywords_reduced = [keyword[0].lower() for keyword in keywords] # get just the word, not the weighting
    return keywords_reduced

def speech_to_text_google(config, audio):
    client = speech.SpeechClient()
    request = client.long_running_recognize(config=config, audio=audio)
    
    response = request.result()

    text = ""
    for result in response.results:
        best_alternative = result.alternatives[0].transcript
        text += best_alternative + " "
    return text

def id3_lookup_helper(id3, tag_name):
    # add a try catch here eventually
    array_of_matches = id3[tag_name]
    if len(array_of_matches) > 0:
        return array_of_matches[0]
    else:
        return 'not found'

class PodcastDetails:
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
    def create(cls, overcast_url, podcast_show_title, podcast_episode_title):
        current_date_string = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %Z")
        simple_description = 'An excerpt from ' + podcast_show_title + ' episode ' + podcast_episode_title + '. Continue listening on <a href="' + overcast_url + '">Overcast</a>'
        podcast_title = generate_acronym(podcast_show_title) + ": "
        return cls(podcast_title,current_date_string,overcast_url,'make a custom but deterministic guid', '',
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

def get_sanitized_mp3_name(text):
    trim_timesamp = re.search('^(.*[\\\/])', text).group(0)
    remove_special_characters =  re.sub('\W+', '', trim_timesamp) + ".mp3"
    return remove_special_characters


def pull_mp3_from_overcast(overcast_url, filename):
    web_page = urllib.request.urlopen(overcast_url).read().decode()
    mp3_link = re.search('https.*mp3', web_page).group(0)
    mp3_bytes = urllib.request.urlopen(mp3_link).read()
    mp3_file = open(filename, 'wb')
    mp3_file.write(mp3_bytes)
    return "" 
    # TODO refactor - OvercastBookmark.get_title_from_overcast_page(None, web_page)



def log_info (text):
    current_date_string = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %Z")
    print (current_date_string + " - " + text)


def store_overcast_timestamp(overcast_url, added_by, store:GoogleDatastore):
    oc_bookmark = OvercastBookmark(overcast_url, added_by, False, None)
    store.store_entry(oc_bookmark.id, oc_bookmark)    

def convert_overcast_timestamps_to_bookmarks(overcast_web_fetcher:OvercastDetailsFetcher, store:GoogleDatastore, app_cache:AppCache ):
    all_podcast_bookmarks = store.get_unprocessed("OvercastBookmark", "processed")

    for overcast_bookmark_entity in all_podcast_bookmarks:
        overcast_bookmark = EntityConversionHelper.overcast_bookmark_from_entity(overcast_bookmark_entity, overcast_web_fetcher)

        podcast_result = app_cache.podcast_cache.try_get_value(overcast_bookmark.get_show_title())
        if not podcast_result.is_found:
            podcast = Podcast("", True, overcast_bookmark.get_show_title())
            app_cache.podcast_cache.add_to_dictionary(overcast_bookmark.get_show_title(), podcast)
            store.store_entry(podcast.id, podcast) # TODO .. only store if it doesn't exist already
        else:
            podcast = podcast_result.value

        episode_result = app_cache.episode_cache.try_get_value(overcast_bookmark.get_episode_title())
        if not episode_result.is_found:
            episode = Episode(podcast.id, overcast_bookmark.get_episode_title())
            app_cache.episode_cache.add_to_dictionary(overcast_bookmark.get_episode_title(), episode)
            store.store_entry(episode.id, episode) # TODO .. only store if it doesn't exist already
        else:
            episode = episode_result.value

        bookmark = Bookmark(episode.id, overcast_bookmark.timestamp, overcast_bookmark.added_by, "Overcast", overcast_bookmark.id, overcast_bookmark.unix_timestamp, False)
        store.store_entry(bookmark.id, bookmark)
        overcast_bookmark.is_processed = True
        store.store_entry(overcast_bookmark.id, overcast_bookmark)
        

def group_unprocessed_clips(store:GoogleDatastore):
    all_podcast_bookmarks = store.get_unprocessed("Bookmark", "is_processed")

    podcasts_episodes = {}

    for bookmark_entity in all_podcast_bookmarks:
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
            new_clip = Clip.from_date_times(episode, clips[0], clips[-1], False, hash, len(clips))
            store.store_entry(new_clip.id, new_clip)    
            
        for bookmark in podcasts_episodes[episode]:
            bookmark.is_processed = True
            store.store_entry(bookmark.id, bookmark)

def grab_clips(store:GoogleDatastore):
        unprocessed_clip_entities = store.get_unprocessed("Clip", "is_processed")

        for entity in unprocessed_clip_entities: 
            clip = EntityConversionHelper.clip_from_entity(entity)
            # look up episode from rss feed
            episode_entity = store.get_entity_by_key(clip.fk_episode_id, 'Episode')
            episode = EntityConversionHelper.episode_from_entity(episode_entity)

            podcast_entity = store.get_entity_by_key(episode.fk_show_id, 'Podcast')
            podcast = EntityConversionHelper.podcast_from_entity(podcast_entity)

            if podcast.rss_feed_url is None or podcast.rss_feed_url == '':
                continue 

            clip.is_processed = True
            store.store_entry(clip.id, clip)

def get_mp3_from_rss_url(episode_name, rss_url):
    return 0 # TODO

def get_mp3_from_overcast(overcast_url): # TODO update to receive clip details
    timestamp = re.search('([^\/]+$)', overcast_url).group(0)
    guid = pseudo_random_uuid(overcast_url)
    guid_string = str(guid)
    project_name = 'personalpodcastfeed'
    bucket_name = 'podcast_feed'
    storage_client = storage.Client(project_name)
    bucket = storage_client.bucket(bucket_name)
    feed_blob = bucket.blob(PODCAST_XML_FILE)
    rss_xml_string = feed_blob.download_as_text()

    if guid_string in rss_xml_string: 
        return     # break if rss xml string already contains guid

    full_mp3_file_name = get_sanitized_mp3_name(overcast_url)

    full_mp3_blob = bucket.blob(full_mp3_file_name)

    log_info ("Grabbing mp3...")
    podcast_page_title = ''
    if not full_mp3_blob.exists():
        podcast_page_title = pull_mp3_from_overcast(overcast_url, full_mp3_file_name)
        full_mp3_blob.upload_from_filename(full_mp3_file_name)
    else:
        podcast_page_title = OvercastBookmark.get_episode_title(overcast_url)
        full_mp3_blob.download_to_filename(full_mp3_file_name)

    podcast_page_title_components = podcast_page_title.split('&mdash;', 2)
    podcast_episode_title = podcast_page_title_components[0].strip().replace('&ndash;', '-')
    podcast_show_title = podcast_page_title_components[1].strip()

    file_friendly_timestamp = timestamp.replace(':', '')
    minutesToGrab = 2
    start_minute_string = get_start_timestamp(timestamp, minutesToGrab)
    end_minute_string = parse_overcast_timestamp(timestamp).strftime('%H:%M:%S')
    podcast = PodcastDetails.create(overcast_url, podcast_show_title, podcast_episode_title)
    unique_file_title = file_friendly_timestamp + re.sub('\W+', '', ((podcast.episode_title+podcast.podcaster)[:50]))
    temp_flac_title = "temp-" + unique_file_title + ".flac"

    log_info("Trimming clip...")
    commands = ['ffmpeg', '-y', '-i', full_mp3_file_name, '-ss', start_minute_string, '-to', end_minute_string, '-f', 'flac', temp_flac_title]
    subprocess.run(commands)

    log_info ("Getting channel count...")
    flac_channel_count = int((subprocess.run(['ffprobe', '-i', temp_flac_title, '-show_entries', 'stream=channels', '-select_streams', 'a:0', '-of', 'compact=p=0:nk=1', '-v', '0'], capture_output=True, text=True).stdout).rstrip('\n'))
    mp3_duration_seconds = minutesToGrab * 60
    
    log_info ("Getting speech-to-text...")
    temp_flac_blob = bucket.blob(temp_flac_title)
    temp_flac_blob.upload_from_filename(temp_flac_title)
    gsutil_uri = 'gs://' + bucket_name + '/' + temp_flac_title
    text_for_audio = speech_to_text(gsutil_uri, flac_channel_count)
    
    log_info ("Getting title and art...")
    top_words = " ".join(((", ".join(get_top_keywords(text_for_audio))).capitalize()).split()[:10])
    podcast.title = podcast.title + top_words
    image_search_local_file_name = image_search(top_words + " clip art")
    image_blob = bucket.blob(image_search_local_file_name)
    image_blob.upload_from_filename(image_search_local_file_name)
    podcast.displayImageLink = image_blob.public_url

    temp_text_to_speech_file = top_words+'speech.mp3'
    temp_intro_file = top_words+'_intro.mp3'
    temp_intro_combined_file = top_words+'combined.mp3'

    log_info ("Mixing intro...")
    text_to_speech(temp_text_to_speech_file, "Welcome! This is:" + top_words + "! " + 'An excerpt from ' + podcast.podcaster + '. Episode: ' + podcast.episode_title)
    commands = ['ffmpeg', '-i', 'intro2.mp3', '-i', temp_text_to_speech_file, '-filter_complex', '[1:a:0]adelay=3000[a1];[a1]volume=volume=2.5[aa1];[0:a:0][aa1]amix=inputs=2[a]', '-map', '[a]', '-y', temp_intro_file]
    subprocess.run(commands)
    commands = ['ffmpeg', '-i', temp_flac_title, '-i', temp_intro_file, '-i', 'outro.mp3', '-filter_complex', '[1:a:0][0:a:0][2:a:0]concat=n=3:v=0:a=1[out]', '-map', '[out]', '-y', temp_intro_combined_file]    
    subprocess.run(commands)

    log_info ("Creating final mp3...")
    unique_mp3_title = unique_file_title + ".mp3" 
    commands = ['ffmpeg', '-y', '-i', temp_intro_combined_file, '-i', image_search_local_file_name, '-map', '1', '-map', '0', '-ab', '320k', '-map_metadata', '0', '-id3v2_version', '3', '-disposition:0', 'attached_pic', '-y', unique_mp3_title ]
    subprocess.run(commands)

    file = ID3(unique_mp3_title)
    with open(image_search_local_file_name, 'rb') as albumart:
        file.add(APIC(
            encoding=3,
            mime='image/jpeg',
            type=3, desc=u'Cover',
            data=albumart.read()
        ))

    log_info("Uploading to bucket...")
    mp3_blob = bucket.blob(unique_mp3_title)
    mp3_blob.upload_from_filename(unique_mp3_title)

    podcast.lengthBytes = os.path.getsize(unique_mp3_title)
    podcast.durationString = "{:0>8}".format(str(timedelta(seconds=mp3_duration_seconds)))
    podcast.guid = guid
    podcast.descriptionHtml = podcast.descriptionHtml + "<br/>" + "<br/>" + text_for_audio
    podcast.mp3Link = mp3_blob.public_url

    log_info ("Adding to podcast feed...")
    rss = ET.fromstring(rss_xml_string)
    channel = rss.find('channel') 
    podcast_xml_subelement = ET.fromstring(create_new_podcast_entry(podcast)).find('item')
    channel.append(podcast_xml_subelement)
    with open(PODCAST_XML_FILE, 'wb') as file:
        tree = ET.ElementTree(rss)
        tree.write(file)  
    feed_blob.upload_from_filename(PODCAST_XML_FILE)

    log_info ("Cleaning up...")
    os.remove(temp_flac_title)
    os.remove(temp_intro_file)
    os.remove(temp_intro_combined_file)
    os.remove(temp_text_to_speech_file)
    os.remove(unique_mp3_title)
    os.remove(image_search_local_file_name)
    os.remove(full_mp3_file_name)
    temp_flac_blob.delete()

def image_search(text):
    text = urllib.parse.quote(text.encode('utf-8'))
    headers = {}
    headers['User-Agent'] = "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36"
    url = "https://www.google.com/search?q=" +text + "&tbm=isch"
    req = urllib.request.Request(url, headers=headers)
    web_page = urllib.request.urlopen(req).read().decode()
    image_url = "https://encrypted" + re.search('(?<=src="https://encrypted)(.*?)(?=")', web_page).group(0)
    req = urllib.request.Request(image_url, headers=headers)
    image_bytes = urllib.request.urlopen(req).read()
    file_name = text+".jpeg"
    image_file = open(file_name, 'wb')
    image_file.write(image_bytes)
    return file_name

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

def text_to_speech(file_name, text_to_speak):
    # Instantiates a client
    client = texttospeech.TextToSpeechClient()

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=text_to_speak)

    # Build the voice request, select the language code ("en-US") and the ssml
    # voice gender ("neutral")
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )

    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # The response's audio_content is binary.
    with open(file_name, "wb") as out:
        # Write the response to the output file.
        out.write(response.audio_content)