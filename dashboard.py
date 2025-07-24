from flask import Flask, render_template
import json
import os

app = Flask(__name__)

STATS_FILE = 'stats.json'

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {'songs_played': 0, 'guild_queues': {}, 'most_played': {}}
    return {'songs_played': 0, 'guild_queues': {}, 'most_played': {}}

@app.route('/')
def index():
    stats = load_stats()
    # Sort most_played songs by play count
    most_played_sorted = sorted(stats.get('most_played', {}).items(), key=lambda item: item[1], reverse=True)
    stats['most_played_sorted'] = most_played_sorted
    return render_template('index.html', stats=stats)

if __name__ == '__main__':
    app.run(port=5000, debug=True) 