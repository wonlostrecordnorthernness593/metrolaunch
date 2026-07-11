import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

import time
import urllib.request
import urllib.parse
import ssl

PORT = 8088

DISCOGS_KEY = ""
DISCOGS_SECRET = ""

# global state for debouncing and caching cover art
global_state = {
    "track": None,
    "artist": None,
    "last_change_time": 0,
    "cover_url": None,
    "is_fetching": False
}

def fetch_discogs_cover(artist, track):
    try:
        query = urllib.parse.quote(f"{artist} {track}")
        url = f"https://api.discogs.com/database/search?q={query}&type=release"
        
        req = urllib.request.Request(url, headers={
            'User-Agent': 'MetroLaunchIOS/1.0',
            'Authorization': f'Discogs key={DISCOGS_KEY}, secret={DISCOGS_SECRET}'
        })
        
        # create an unverified SSL context to bypass macOS cert issues
        context = ssl._create_unverified_context()

        with urllib.request.urlopen(req, timeout=5, context=context) as response:
            data = json.loads(response.read().decode())
            results = data.get('results', [])
            if results:
                # Discogs `cover_image` is usually the full size, `thumb` is smaller.
                cover = results[0].get('cover_image')
                if cover and "spacer.gif" not in cover:
                    return cover
    except Exception as e:
        print(f"Error fetching from Discogs...")
    return 'FAILED'

def get_spotify_status_local():
    script = '''
    tell application "System Events"
        set processList to (name of every process)
    end tell

    if processList contains "Spotify" then
        tell application "Spotify"
            if player state is playing then
                set trackName to name of current track
                set artistName to artist of current track
                return "PLAYING|" & trackName & "|" & artistName
            else
                return "PAUSED"
            end if
        end tell
    else
        return "NOT_RUNNING"
    end if
    '''
    try:
        result = subprocess.check_output(['osascript', '-e', script])
        result = result.decode('utf-8').strip()
        
        if result == "NOT_RUNNING" or result == "PAUSED":
            return {"isPlaying": False}
        
        if result.startswith("PLAYING|"):
            parts = result.split("|")
            track = parts[1]
            artist = parts[2]
            
            # check for track change
            if global_state["track"] != track or global_state["artist"] != artist:
                global_state["track"] = track
                global_state["artist"] = artist
                global_state["last_change_time"] = time.time()
                global_state["cover_url"] = None
                global_state["is_fetching"] = False
            
            # if 2 seconds have passed since the track started/changed, fetch cover
            if global_state["cover_url"] is None and not global_state["is_fetching"]:
                if time.time() - global_state["last_change_time"] >= 2.0:
                    global_state["is_fetching"] = True
                    print(f"Song {artist} - {track}")
                    print(f"Fetching cover art from Discogs...")
                    cover = fetch_discogs_cover(artist, track)
                    if cover and cover != 'FAILED':
                        print(f"Found cover art...")
                    else:
                        print("No cover art found...")
                    print(f" ")
                    global_state["cover_url"] = cover
                    global_state["is_fetching"] = False

            return {
                "isPlaying": True,
                "track": track,
                "artist": artist,
                "coverUrl": f"/spotify/cover?t={int(global_state['last_change_time'])}" if global_state["cover_url"] and global_state["cover_url"] != 'FAILED' else None
            }
            
    except Exception as e:
        print(f"Error checking Spotify status: {e}")
        return {"isPlaying": False}
    
    return {"isPlaying": False}

class SpotifyStatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/spotify':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*') # allow PWA to read it
            self.end_headers()
            
            status = get_spotify_status_local()
            self.wfile.write(json.dumps(status).encode('utf-8'))
        elif self.path.startswith('/spotify/cover'):
            url = global_state.get('cover_url')
            if url and url != 'FAILED':
                req = urllib.request.Request(url, headers={'User-Agent': 'MetroLaunchIOS/1.0'})
                context = ssl._create_unverified_context()
                try:
                    with urllib.request.urlopen(req, timeout=5, context=context) as response:
                        img_data = response.read()
                        self.send_response(200)
                        self.send_header('Content-type', 'image/jpeg')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Cache-Control', 'public, max-age=86400')
                        self.end_headers()
                        self.wfile.write(img_data)
                except Exception as e:
                    print(f"Error Proxying Image...")
                    self.send_error(500)
            else:
                self.send_error(404)
        else:
            self.send_response(404)
            self.end_headers()

    # handle preflight CORS requests quietly
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

def run_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, SpotifyStatusHandler)
    print(f"Spotify Local Status Server running on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        print("Server stopped...")

if __name__ == '__main__':
    run_server()
