import os
from flask import Flask, render_template, request
from objects.google_datastore import GoogleDatastore
from objects.overcast_details_fetcher import OvercastDetailsFetcher
from objects.app_cache import AppCache
from get_snippet_from_overcast import group_unprocessed_clips, store_overcast_timestamp, convert_overcast_timestamps_to_bookmarks

app = Flask(__name__)

overcast_web_fetcher = OvercastDetailsFetcher(100)
store = GoogleDatastore()
app_cache = AppCache(100)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add-clip', methods=['POST'])
def add_clip():
    content = request.get_json()
    convert_overcast_timestamps_to_bookmarks(overcast_web_fetcher, store, app_cache)
    store_overcast_timestamp(content['targetUrl'], content['addedBy'], store)
    group_unprocessed_clips(store)
    return '', 200

# os.chdir("temp-files")

app.run(host='0.0.0.0', port=81)