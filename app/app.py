from datetime import datetime
import os
from flask import Flask, Response, render_template, request, stream_with_context
from objects.episode_clipping_service import EpisodeClippingService
from objects.bucket_manager import BucketManager
from objects.google_datastore import GoogleDatastore
from objects.overcast_details_fetcher import OvercastDetailsFetcher
from objects.app_cache import AppCache
from objects.open_ai_api import OpenAIApi
from objects.summarization_service import SummarizationService
from get_snippet_from_overcast import add_clip_to_feed, create_new_podcast_feed, reprocess_clip_audio, redo_topic_summary_for_clip, add_clip_summaries, group_unprocessed_clips,get_top_clips, store_overcast_timestamp, convert_overcast_timestamps_to_bookmarks, grab_clips, clean_up_episode_names

web_app = Flask(__name__)

overcast_web_fetcher = OvercastDetailsFetcher(100)
store = GoogleDatastore()
app_cache = AppCache(100)
open_ai_api = OpenAIApi()
bucket_manager = BucketManager('personalpodcastfeed', 'podcast_feed')
summarization_service = SummarizationService(open_ai_api)
episode_clipping_service = EpisodeClippingService(bucket_manager, summarization_service)
#temp_folder_name = "temp-files" + str(datetime.now().strftime("%a%d%b%Y%H%M%S"))
#os.mkdir(temp_folder_name)
#print (os.getcwd())
os.chdir("app/temp-files") # TODO - gotta figure out how to fix this on live version

@web_app.route('/')
def index():
    return render_template('index.html')

@web_app.route('/add-overcast-bookmark', methods=['POST'])
def add_clip():
    content = request.get_json()
    store_overcast_timestamp(content['targetUrl'], content['addedBy'], store)
    return '', 200

@web_app.route('/convert-overcast-bookmarks', methods=['POST'])
def convert_overcast_bookmarks():
    convert_overcast_timestamps_to_bookmarks(overcast_web_fetcher, store, app_cache)
    return '', 200

@web_app.route('/group-clips', methods=['POST'])
def group_clips():
    group_unprocessed_clips(store)
    return '', 200

@web_app.route('/grab-clips', methods=['POST'])
def sample_clips():
    clean_up_episode_names(store)
    grab_clips(store, episode_clipping_service)
    return '', 200

@web_app.route('/get_top_clips', methods=['GET'])
def get_the_top_clips():
    return Response(stream_with_context(get_top_clips(store)))

@web_app.route('/add_clip_summaries', methods=['POST'])
def summarize_clips():
    add_clip_summaries(store, open_ai_api)
    return '', 200

@web_app.route('/clip/<clip_id>/generate_topic', methods=['POST'])
def generate_topic(clip_id):
    new_clip_name = redo_topic_summary_for_clip(clip_id, store, summarization_service)
    return 'new clip name: ' + new_clip_name , 200

@web_app.route('/clip/<clip_id>/reprocess', methods=['POST'])
def reprocess_clip(clip_id):
    reprocess_clip_audio(clip_id, store, episode_clipping_service)
    return '', 200

@web_app.route('/feed/create', methods=['POST'])
def create_feed():
    content = request.get_json()
    create_new_podcast_feed(content['feed_name'], bucket_manager)
    return '', 200

@web_app.route('/feed/<feed_name>/add_clip/<clip_id>', methods=['POST'])
def add_clip_to_podcast_feed(feed_name, clip_id):
    add_clip_to_feed(feed_name, clip_id, bucket_manager, store)
    return '', 200

if __name__ == "__main__":
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))