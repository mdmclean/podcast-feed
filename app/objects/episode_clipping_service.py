from datetime import datetime
import os
import re
import subprocess
import urllib.request
import urllib.parse
from objects.clip import Clip
from objects.summarization_service import SummarizationService
from objects.summarization_result import SummarizationResult
from objects.bucket_manager import BucketManager
from objects.cut_and_transcribe_result import CutAndTransribeResult
import yake
from mutagen.id3 import APIC, ID3
from google.cloud import texttospeech, speech_v1p1beta1 as speech

class EpisodeClippingService:
    def __init__(self, bucket_manager:BucketManager, summarization_service:SummarizationService):
        self.bucket_manager = bucket_manager
        self.summarization_service = summarization_service

    def remove_special_characters(self, text):
        remove_special_characters =  re.sub('\W+', '', text)
        return remove_special_characters

    def log_info (self, text):
        current_date_string = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %Z")
        print (current_date_string + " - " + text)

    def speech_to_text(self,clip_gs_link, channel_count):
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

        text = self.speech_to_text_google(config, audio)
        return text

    def get_top_keywords (self,text):
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

    def speech_to_text_google(self, config, audio):
        client = speech.SpeechClient()
        request = client.long_running_recognize(config=config, audio=audio)
        
        response = request.result()

        text = ""
        for result in response.results:
            best_alternative = result.alternatives[0].transcript
            text += best_alternative + " "
        return text

    def image_search(self, text):
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

    def text_to_speech(self, file_name, text_to_speak):
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

    def cut_and_transcribe_clip(self, episode_mp3_url:str, clip:Clip, process_text:bool, podcast_name:str, episode_name:str): # TODO update to receive clip details
        result:CutAndTransribeResult = CutAndTransribeResult(None, None, None, None, None,None,None,None)

        self.log_info ("Downloading mp3 to file system...")
        full_mp3_file_name = self.remove_special_characters(episode_name) +".mp3"
        full_mp3_blob = self.bucket_manager.get_blob(full_mp3_file_name)
        self.download_mp3(episode_mp3_url, full_mp3_file_name, full_mp3_blob)

        file_friendly_timestamp = clip.clip_start.replace(':', '')
        unique_file_title = file_friendly_timestamp + re.sub('\W+', '', ((episode_name+podcast_name)[:50]))
        temp_flac_title = "temp-" + unique_file_title + ".flac"

        self.log_info("Trimming clip...")
        commands = ['ffmpeg', '-y', '-i', full_mp3_file_name, '-ss', clip.clip_start, '-to', clip.clip_end, '-f', 'flac', temp_flac_title]
        subprocess.run(commands)

        self.log_info ("Getting channel count...")
        flac_channel_count = int((subprocess.run(['ffprobe', '-i', temp_flac_title, '-show_entries', 'stream=channels', '-select_streams', 'a:0', '-of', 'compact=p=0:nk=1', '-v', '0'], capture_output=True, text=True).stdout).rstrip('\n'))

        self.log_info ("Getting speech-to-text...")
        full_text_blob = self.bucket_manager.get_blob(unique_file_title + "-transcript" +".txt")
        text_for_audio = ""
        if full_text_blob.exists():
            text_for_audio = full_text_blob.download_as_text()
        else: 
            temp_flac_blob = self.bucket_manager.get_blob(temp_flac_title)
            temp_flac_blob.upload_from_filename(temp_flac_title)
            gsutil_uri = 'gs://' + self.bucket_manager.get_bucket_name() + '/' + temp_flac_title
            text_for_audio = self.speech_to_text(gsutil_uri, flac_channel_count)
            temp_flac_blob.delete()
            full_text_blob.upload_from_string(text_for_audio)
        
        summarization_result = SummarizationResult(None,None,None)
        if process_text:
            summarization_result = self.summarization_service.summarize(text_for_audio)

            reduced_text_blob = self.bucket_manager.get_blob(unique_file_title + "-reduced" +".txt")
            reduced_text_blob.upload_from_string(summarization_result.reduced_text)
            result.reduced_text_url = reduced_text_blob.public_url

            summary_text_blob = self.bucket_manager.get_blob(unique_file_title + "-summary" +".txt")
            summary_text_blob.upload_from_string(summarization_result.summary_text)
            result.summary_text_url = summary_text_blob.public_url
        else:
            summarization_result.topic = clip.topic

        

        result.topic = summarization_result.topic

        self.log_info ("Getting title and art...")
        top_words = " ".join(((", ".join(self.get_top_keywords(text_for_audio))).capitalize()).split()[:10])

        result.top_ngrams = top_words
        result.full_text_url = full_text_blob.public_url

        image_search_local_file_name = self.image_search(top_words + " clip art")
        image_blob = self.bucket_manager.get_blob(image_search_local_file_name)
        image_blob.upload_from_filename(image_search_local_file_name)
        result.image_url = image_blob.public_url

        temp_text_to_speech_file = top_words+'speech.mp3'
        temp_intro_file = top_words+'_intro.mp3'
        temp_intro_combined_file = top_words+'combined.mp3'

        self.log_info ("Mixing intro...")
        self.text_to_speech(temp_text_to_speech_file, "Welcome! This is:" + result.topic + "! " + 'An excerpt from ' + podcast_name + '. Episode: ' + episode_name)
        commands = ['ffmpeg', '-i', 'intro2.mp3', '-i', temp_text_to_speech_file, '-filter_complex', '[1:a:0]adelay=3000[a1];[a1]volume=volume=2.5[aa1];[0:a:0][aa1]amix=inputs=2[a]', '-map', '[a]', '-y', temp_intro_file]
        subprocess.run(commands)
        commands = ['ffmpeg', '-i', temp_flac_title, '-i', temp_intro_file, '-i', 'outro.mp3', '-filter_complex', '[1:a:0][0:a:0][2:a:0]concat=n=3:v=0:a=1[out]', '-map', '[out]', '-y', temp_intro_combined_file]    
        subprocess.run(commands)

        self.log_info ("Creating final mp3...")
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

        self.log_info("Uploading to bucket...")
        mp3_blob = self.bucket_manager.get_blob(unique_mp3_title)
        mp3_blob.upload_from_filename(unique_mp3_title)

        result.mp3_url = mp3_blob.public_url

        self.log_info ("Cleaning up...")
        os.remove(temp_flac_title)
        os.remove(temp_intro_file)
        os.remove(temp_intro_combined_file)
        os.remove(temp_text_to_speech_file)
        os.remove(unique_mp3_title)
        os.remove(image_search_local_file_name)
        os.remove(full_mp3_file_name)
        return result

    def download_mp3(self, mp3_location, full_mp3_file_name, full_mp3_blob):
        if not full_mp3_blob.exists():
            self.pull_mp3(mp3_location, full_mp3_file_name)
            full_mp3_blob.upload_from_filename(full_mp3_file_name)
        else:
            full_mp3_blob.download_to_filename(full_mp3_file_name)

    def pull_mp3(self, mp3_url, temp_file_location):
        mp3_bytes = urllib.request.urlopen(mp3_url).read()
        mp3_file = open(temp_file_location, 'wb')
        mp3_file.write(mp3_bytes)
