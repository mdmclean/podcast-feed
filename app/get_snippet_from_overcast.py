import os
import subprocess
import sys
import urllib.request
import urllib.parse
import re
import math
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
from objects.mp3_fetcher import Mp3Fetcher
from objects.cut_and_transcribe_result import CutAndTransribeResult
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
    config.diarization_config = diarization_config

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

def remove_special_characters(text):
    remove_special_characters =  re.sub('\W+', '', text)
    return remove_special_characters


def pull_mp3_from_overcast(overcast_url, filename):
    web_page = urllib.request.urlopen(overcast_url).read().decode()
    mp3_link = re.search('https.*mp3', web_page).group(0)
    mp3_bytes = urllib.request.urlopen(mp3_link).read()
    mp3_file = open(filename, 'wb')
    mp3_file.write(mp3_bytes)
    return "" 
    # TODO refactor - OvercastBookmark.get_title_from_overcast_page(None, web_page)

def pull_mp3(mp3_url, temp_file_location):
    mp3_bytes = urllib.request.urlopen(mp3_url).read()
    mp3_file = open(temp_file_location, 'wb')
    mp3_file.write(mp3_bytes)

def log_info (text):
    current_date_string = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %Z")
    print (current_date_string + " - " + text)


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
    all_podcast_bookmarks = store.get_unprocessed("OvercastBookmark", "processed")

    for overcast_bookmark_entity in all_podcast_bookmarks:
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

def grab_clips(store:GoogleDatastore):
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
                    result:CutAndTransribeResult = cut_and_transcribe_clip(episode.mp3_url, clip.clip_start, clip.clip_end, podcast.show_name, episode.episode_name)
                    clip.full_text_url = result.full_text_url
                    clip.top_ngrams = result.top_ngrams
                    clip.mp3_url = result.mp3_url
                    clip.size_bytes = result.mp3_size_bytes
                    clip.image_url = result.image_url
                    clip.updated_unix_timestamp = time.time()
                    clip.is_processed = True
                    store.store_entry(clip.id, clip)
                except Exception as e: 
                    print ("failed for " + episode.episode_name + " - " + str(e))


def get_number_bookmarks(clip:Clip):
    return clip.number_of_bookmarks

def get_top_clips(store:GoogleDatastore):
    clip_entities = store.get_all("Clip")

    clips = [EntityConversionHelper.clip_from_entity(clip) for clip in clip_entities]

    clips.sort(reverse=True, key=get_number_bookmarks)

    yield "<style type='text/css'>.myTable { background-color:#eee;border-collapse:collapse; }.myTable th { background-color:#000;color:white;width:50%; }.myTable td, .myTable th { padding:5px;border:1px solid #000; }</style>"
    yield "<table class='myTable'><th>Number of bookmarks</th><th>Podcast</th><th>Episode</th><th>Start Time</th><th>Length</th><th>Episode Link</th><th>Clip Link</th><th>ngram</th><th>Full text link</th>"

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

        minutes_to_listen_to = math.ceil((parse_overcast_timestamp(clip.clip_end) - parse_overcast_timestamp(clip.clip_start)).total_seconds() / 60)

        yield "<tr>"
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
            yield "<td><a href='"+ str(clip.mp3_url) + "'>link</a></td>"
        else:
            yield "<td>no link</td>"
        yield "<td>" + str(clip.top_ngrams) + "</td>"
        if clip.full_text_url is not None:
            yield "<td><a href='"+ str(clip.full_text_url) + "'>link</a></td>"
        else:
            yield "<td>no link</td>"
        yield "</tr> "

    yield "</ul>"



def add_clip_to_personal_feed(clip:Clip, episode:Episode, podcast:Podcast):
    guid_string = str(clip.id)
    project_name = 'personalpodcastfeed'
    bucket_name = 'podcast_feed'
    storage_client = storage.Client(project_name)
    bucket = storage_client.bucket(bucket_name)
    feed_blob = bucket.blob(PODCAST_XML_FILE)
    rss_xml_string = feed_blob.download_as_text()

    if guid_string in rss_xml_string: 
        return ""    # break if rss xml string already contains guid

    mp3_duration_seconds = math.ceil((parse_overcast_timestamp(clip.clip_end) - parse_overcast_timestamp(clip.clip_start)).total_seconds() / 60)

    podcast = PodcastDetails.create(episode.mp3_url, podcast.show_name, episode.episode_name)
    podcast.lengthBytes = clip.size_bytes
    podcast.durationString = "{:0>8}".format(str(timedelta(seconds=mp3_duration_seconds)))
    podcast.guid = clip.id
    text_blob = bucket.from_string(clip.full_text_url)
    text_for_audio = text_blob.download_as_texT()
    podcast.descriptionHtml = podcast.descriptionHtml + "<br/>" + "<br/>" + text_for_audio
    podcast.mp3Link = clip.mp3_url
    podcast.title = clip.top_ngrams
    podcast.displayImageLink = clip.image_url
    
    log_info ("Adding to podcast feed...")
    rss = ET.fromstring(rss_xml_string)
    channel = rss.find('channel') 
    podcast_xml_subelement = ET.fromstring(create_new_podcast_entry(podcast)).find('item')
    channel.append(podcast_xml_subelement)
    with open(PODCAST_XML_FILE, 'wb') as file:
        tree = ET.ElementTree(rss)
        tree.write(file)  

    feed_blob.upload_from_filename(PODCAST_XML_FILE)

def clean_up_episode_names (store:GoogleDatastore):
    episode_entries = store.get_all("Episode")

    episodes = [EntityConversionHelper.episode_from_entity(ep) for ep in episode_entries]

    for ep in episodes: 
        ep.episode_name = ep.episode_name.replace("&rsquo;", "'")
        store.store_entry(ep.id, ep)
        

def cut_and_transcribe_clip(mp3_location, start_time, end_time, podcast_name, episode_name): # TODO update to receive clip details
    result:CutAndTransribeResult = CutAndTransribeResult(None, None, None, None, None)
    full_mp3_file_name = remove_special_characters(episode_name) +".mp3"
    project_name = 'personalpodcastfeed'
    bucket_name = 'podcast_feed'
    storage_client = storage.Client(project_name)
    bucket = storage_client.bucket(bucket_name)
    full_mp3_blob = bucket.blob(full_mp3_file_name)

    log_info ("Grabbing mp3...")
    if not full_mp3_blob.exists():
        pull_mp3(mp3_location, full_mp3_file_name)
        full_mp3_blob.upload_from_filename(full_mp3_file_name)
    else:
        full_mp3_blob.download_to_filename(full_mp3_file_name)

    file_friendly_timestamp = start_time.replace(':', '')
    unique_file_title = file_friendly_timestamp + re.sub('\W+', '', ((episode_name+podcast_name)[:50]))
    temp_flac_title = "temp-" + unique_file_title + ".flac"

    log_info("Trimming clip...")
    commands = ['ffmpeg', '-y', '-i', full_mp3_file_name, '-ss', start_time, '-to', end_time, '-f', 'flac', temp_flac_title]
    subprocess.run(commands)

    log_info ("Getting channel count...")
    flac_channel_count = int((subprocess.run(['ffprobe', '-i', temp_flac_title, '-show_entries', 'stream=channels', '-select_streams', 'a:0', '-of', 'compact=p=0:nk=1', '-v', '0'], capture_output=True, text=True).stdout).rstrip('\n'))

    log_info ("Getting speech-to-text...")
    full_text_blob = bucket.blob(unique_file_title + "-transcript" +".txt")
    text_for_audio = ""
    if full_text_blob.exists():
        text_for_audio = full_text_blob.download_as_text()
    else: 
        temp_flac_blob = bucket.blob(temp_flac_title)
        temp_flac_blob.upload_from_filename(temp_flac_title)
        gsutil_uri = 'gs://' + bucket_name + '/' + temp_flac_title
        text_for_audio = speech_to_text(gsutil_uri, flac_channel_count)
        temp_flac_blob.delete()
        full_text_blob.upload_from_string(text_for_audio)
    
    log_info ("Getting title and art...")
    top_words = " ".join(((", ".join(get_top_keywords(text_for_audio))).capitalize()).split()[:10])

    result.top_ngrams = top_words
    result.full_text_url = full_text_blob.public_url

    image_search_local_file_name = image_search(top_words + " clip art")
    image_blob = bucket.blob(image_search_local_file_name)
    image_blob.upload_from_filename(image_search_local_file_name)
    result.image_url = image_blob.public_url

    temp_text_to_speech_file = top_words+'speech.mp3'
    temp_intro_file = top_words+'_intro.mp3'
    temp_intro_combined_file = top_words+'combined.mp3'

    log_info ("Mixing intro...")
    text_to_speech(temp_text_to_speech_file, "Welcome! This is:" + top_words + "! " + 'An excerpt from ' + podcast_name + '. Episode: ' + episode_name)
    commands = ['ffmpeg', '-i', 'intro2.mp3', '-i', temp_text_to_speech_file, '-filter_complex', '[1:a:0]adelay=3000[a1];[a1]volume=volume=2.5[aa1];[0:a:0][aa1]amix=inputs=2[a]', '-map', '[a]', '-y', temp_intro_file]
    subprocess.run(commands)
    commands = ['ffmpeg', '-i', temp_flac_title, '-i', temp_intro_file, '-i', 'outro.mp3', '-filter_complex', '[1:a:0][0:a:0][2:a:0]concat=n=3:v=0:a=1[out]', '-map', '[out]', '-y', temp_intro_combined_file]    
    subprocess.run(commands)

    log_info ("Creating final mp3...")
    unique_mp3_title = unique_file_title + ".mp3" 
    commands = ['ffmpeg', '-y', '-i', temp_intro_combined_file, '-i', image_search_local_file_name, '-map', '1', '-map', '0', '-ab', '320k', '-map_metadata', '0', '-id3v2_version', '3', '-disposition:0', 'attached_pic', '-y', unique_mp3_title ]
    subprocess.run(commands)

    result.mp3_size_bytes = os.path.getsize(unique_mp3_title)
    
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

    result.mp3_url = mp3_blob.public_url

    log_info ("Cleaning up...")
    os.remove(temp_flac_title)
    os.remove(temp_intro_file)
    os.remove(temp_intro_combined_file)
    os.remove(temp_text_to_speech_file)
    os.remove(unique_mp3_title)
    os.remove(image_search_local_file_name)
    os.remove(full_mp3_file_name)
    return result

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