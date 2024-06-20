import asyncio
import websockets
from datetime import datetime
import os
import base64
import json
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


TIME_THRESHOLD = 10 * 60  # 10 minutes in seconds


def generate_sec_websocket_key():
    random_bytes = os.urandom(16)
    key = base64.b64encode(random_bytes).decode('utf-8')
    return key


def get_readable_time():
    return datetime.now().strftime('%Y%m%d_%H%M%S')


async def save_pairs_to_file(pairs):
    file_created_at = get_readable_time()
    current_directory = os.getcwd()
    filename = os.path.join(
        current_directory, f'dexscreener_{file_created_at}.json')

    with open(filename, 'w') as file:
        json.dump(pairs, file)


def read_pairs_from_file(filename):
    with open(filename, 'r') as file:
        pairs = json.load(file)
    return pairs


async def dexscreener_scraper():
    headers = {
        "Host": "io.dexscreener.com",
        "Connection": "Upgrade",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Upgrade": "websocket",
        "Origin": "https://dexscreener.com",
        "Sec-WebSocket-Version": 13,
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-WebSocket-Key": generate_sec_websocket_key()
    }
    uri = "wss://io.dexscreener.com/dex/screener/pairs/h24/1?rankBy[key]=trendingScoreH6&rankBy[order]=desc"
    async with websockets.connect(uri, extra_headers=headers) as websocket:
        try:
            message_raw = await websocket.recv()
            message = json.loads(message_raw)
            _type = message["type"]
            if _type == 'pairs':
                pairs = message["pairs"]
                print("Pairs fetched from websocket...")
                await save_pairs_to_file(pairs)
        except websockets.ConnectionClosed:
            pass


def get_most_recent_file():
    files = [f for f in os.listdir('.') if f.startswith(
        'dexscreener_') and f.endswith('.json')]
    if not files:
        return None

    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return files[0]


def is_file_older_than_threshold(filename):
    file_mtime = os.path.getmtime(filename)
    file_age = time.time() - file_mtime
    return file_age > TIME_THRESHOLD


async def execute_or_return_old_data():
    recent_file = get_most_recent_file()

    if recent_file and not is_file_older_than_threshold(recent_file):
        print("Returning old data from file.")
        pairs = read_pairs_from_file(recent_file)
        pair_addresses = [pair['pairAddress'] for pair in pairs]
        return pair_addresses
    else:
        print("Executing main function.")
        # await asyncio.run(dexscreener_scraper())
        await dexscreener_scraper()
        recent_file = get_most_recent_file()
        pairs = read_pairs_from_file(recent_file)
        pair_addresses = [pair['pairAddress'] for pair in pairs]
        return pair_addresses


@app.route('/', methods=['GET'])
def root():
    return "Welcome to the Flask API"


@app.route('/pairs', methods=['GET', 'OPTIONS'])
async def pairs():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    elif request.method == 'GET':
        data = await execute_or_return_old_data()
        return jsonify(data)


def _build_cors_preflight_response():
    response = app.make_response('')
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Methods", "GET, OPTIONS")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    return response


if __name__ == '__main__':
    app.run(debug=True, port=5000)
