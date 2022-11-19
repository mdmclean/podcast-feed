import os
from flask import Flask, Response, render_template, request, stream_with_context
from objects.google_datastore import GoogleDatastore
from objects.overcast_details_fetcher import OvercastDetailsFetcher
from objects.app_cache import AppCache
from get_snippet_from_overcast import group_unprocessed_clips,get_top_clips, store_overcast_timestamp, convert_overcast_timestamps_to_bookmarks, grab_clips

app = Flask(__name__)

overcast_web_fetcher = OvercastDetailsFetcher(100)
store = GoogleDatastore()
app_cache = AppCache(100)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add-overcast-bookmark', methods=['POST'])
def add_clip():
    content = request.get_json()
    store_overcast_timestamp(content['targetUrl'], content['addedBy'], store)
    return '', 200

@app.route('/convert-overcast-bookmarks', methods=['POST'])
def convert_overcast_bookmarks():
    convert_overcast_timestamps_to_bookmarks(overcast_web_fetcher, store, app_cache)
    return '', 200

@app.route('/group-clips', methods=['POST'])
def group_clips():
    group_unprocessed_clips(store)
    return '', 200

@app.route('/grab-clips', methods=['POST'])
def sample_clips():
    grab_clips(store)
    return '', 200

@app.route('/get_top_clips', methods=['GET'])
def get_the_top_clips():
    return Response(stream_with_context(get_top_clips(store)))

# os.chdir("podcast-feed/podcast-feed/temp-files")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))