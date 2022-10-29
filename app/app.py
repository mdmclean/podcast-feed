import os
from flask import Flask, render_template, request
from objects.overcast_details_fetcher import OvercastDetailsFetcher
from get_snippet_from_overcast import group_unprocessed_clips, store_overcast_timestamp, convert_overcast_timestamps_to_bookmarks

app = Flask(__name__)

overcast_web_fetcher = OvercastDetailsFetcher()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add-clip', methods=['POST'])
def add_clip():
    content = request.get_json()
    convert_overcast_timestamps_to_bookmarks(overcast_web_fetcher)
    store_overcast_timestamp(content['targetUrl'], content['addedBy'])
    group_unprocessed_clips()
    return '', 200

os.chdir("temp-files")

app.run(host='0.0.0.0', port=81)