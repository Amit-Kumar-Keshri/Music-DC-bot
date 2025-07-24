from flask import Flask, render_template_string
import json
import os

app = Flask(__name__)

STATS_FILE = 'stats.json'

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    return {'songs_played': 0, 'guild_queues': {}, 'most_played': {}}

@app.route('/')
def index():
    stats = load_stats()
    return render_template_string('''
    <h1>Sandesh Music Bot Dashboard</h1>
    <p><b>Total Songs Played:</b> {{ stats['songs_played'] }}</p>
    <h2>Current Queues</h2>
    {% for guild, queue in stats['guild_queues'].items() %}
      <h3>Guild {{ guild }}</h3>
      <ul>
      {% for song in queue %}
        <li>{{ song }}</li>
      {% endfor %}
      </ul>
    {% endfor %}
    <h2>Most Played Songs</h2>
    <ul>
    {% for song, count in stats['most_played'].items()|sort(attribute=1, reverse=True) %}
      <li>{{ song }} ({{ count }} plays)</li>
    {% endfor %}
    </ul>
    ''', stats=stats)

if __name__ == '__main__':
    app.run(port=5000, debug=True) 