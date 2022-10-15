import os
from flask import Flask, render_template, request
from get_snippet_from_overcast import get_mp3_from_overcast

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add-clip', methods=['POST'])
def add_clip():
    content = request.get_json()
    print(content['targetUrl'])
    get_mp3_from_overcast(content['targetUrl'])
    return '', 200

os.chdir("temp-files")

app.run(host='0.0.0.0', port=81)