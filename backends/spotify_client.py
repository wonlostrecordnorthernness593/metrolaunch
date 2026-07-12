#!/usr/bin/env python3
"""
Spotify Client for MetroLaunch (Leopard Server)
========================================
Runs on the Mac alongside Spotify
Detects song changes and pauses via AppleScript, then pushes
the status to a remote PHP server

Usage:
    python3 spotify_client.py
"""

import json
import os
import random
import select
import subprocess
import sys
import termios
import time
import tty
import urllib.error
import urllib.parse
import urllib.request
import ssl

CONFIG_FILE = os.path.expanduser('~/.spotify_leopard_user')

# ── helpers ──

# The server serialises writes with a file lock and can respond 503
_RETRY_STATUSES = {429, 500, 502, 503, 504}


def make_request(url, data=None, method='GET', *, retries=3):
    """Make an HTTP request and return parsed JSON (or None on failure).

    Retries transient network errors and 5xx / 429 responses with jittered
    backoff. Returns None only after all retries are exhausted, or on a
    non-retryable 4xx response.
    """
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'MetroLaunchClient/2.1',
        'Connection': 'close',
    }
    body = json.dumps(data).encode('utf-8') if data else None
    ctx = ssl._create_unverified_context()

    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                raw = resp.read().decode('utf-8')
                try:
                    return json.loads(raw)
                except ValueError:
                    return None
        except urllib.error.HTTPError as e:
            # Retry on server-side backpressure, give up on real client errors
            if e.code in _RETRY_STATUSES and attempt < retries:
                pass
            else:
                return None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if attempt >= retries:
                return None
        # Step off, George...
        time.sleep((0.4 * (2 ** attempt)) + random.uniform(0, 0.25))
    return None


def save_username(username):
    with open(CONFIG_FILE, 'w') as f:
        f.write(username)


def load_username():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            name = f.read().strip()
            if name:
                return name
    return None


def get_spotify_status():
    """Use AppleScript to query Spotify's current state"""
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
        return result.decode('utf-8').strip()
    except Exception:
        return 'NOT_RUNNING'


# ── Main ──

SERVER_URL = 'https://leopardindustries.net:8088/spotify.php'
POLL_RATE = 2

def main():
    server_url = SERVER_URL
    poll_rate = POLL_RATE

    # ── connect to server ──
    print('')
    print('Connecting to the Leopard main server...')
    # test connectivity by hitting the default endpoint
    test = make_request(server_url)
    if test is None:
        print('[FAIL] Could not connect to the Leopard main server')
        print(f'       Tried: {server_url}')
        sys.exit(1)
    print('[OK] Successfully connected to the Leopard main server')
    print('')

    # ── username registration / login ──
    saved_user = load_username()

    if saved_user:
        # try to re register to confirm the user still exists
        resp = make_request(f'{server_url}?action=register', {'username': saved_user}, 'POST')
        if resp and resp.get('ok'):
            username = saved_user
            print(f'[OK] Signed back into server with username {username}...')
        else:
            print(f'[WARN] Saved username "{saved_user}" was rejected by the server...')
            saved_user = None

    if not saved_user:
        print('You need to register a username for this to work')
        print('This will be remembered')
        print('')
        while True:
            try:
                username = input('[ASK] What should your username be - ').strip()
            except (EOFError, KeyboardInterrupt):
                print('')
                sys.exit(0)

            if not username:
                continue

            print('')
            print('Registering new username on server...')
            resp = make_request(f'{server_url}?action=register', {'username': username}, 'POST')
            if resp and resp.get('ok'):
                save_username(username)
                print('[OK] New username registered')
                break
            else:
                error_msg = resp.get('error', 'Unknown error') if resp else 'Server unreachable'
                print(f'[FAIL] Registration failed - {error_msg}')
                print('')

    print('[NFO] Strike \'q\' key to quit the program')
    print('')

    # ── polling loop ──
    prev_track = None
    prev_artist = None
    prev_playing = None

    # put terminal into raw mode for non-blocking key detection
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())

    try:
        while True:
            # check for 'q' keypress (non-blocking)
            if select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                if ch.lower() == 'q':
                    break

            try:
                status = get_spotify_status()

                if status == 'NOT_RUNNING':
                    # if it was playing before, send a pause
                    if prev_playing is True:
                        make_request(f'{server_url}?action=update', {
                            'username': username,
                            'track': '',
                            'artist': '',
                            'isPlaying': False,
                        }, 'POST')
                        print('[Spotify] Detected Spotify closed')
                        prev_playing = False

                elif status == 'PAUSED':
                    if prev_playing is not False:
                        make_request(f'{server_url}?action=update', {
                            'username': username,
                            'track': prev_track or '',
                            'artist': prev_artist or '',
                            'isPlaying': False,
                        }, 'POST')
                        print('[Spotify] Detected song paused')
                        prev_playing = False

                elif status.startswith('PLAYING|'):
                    parts = status.split('|')
                    track = parts[1] if len(parts) > 1 else ''
                    artist = parts[2] if len(parts) > 2 else ''

                    song_changed = (track != prev_track or artist != prev_artist)
                    resumed = (prev_playing is False and not song_changed)

                    if song_changed:
                        print(f'[Spotify] Detected song changed')
                        make_request(f'{server_url}?action=update', {
                            'username': username,
                            'track': track,
                            'artist': artist,
                            'isPlaying': True,
                        }, 'POST')
                    elif resumed:
                        print(f'[Spotify] Detected song resumed')
                        make_request(f'{server_url}?action=update', {
                            'username': username,
                            'track': track,
                            'artist': artist,
                            'isPlaying': True,
                        }, 'POST')

                    prev_track = track
                    prev_artist = artist
                    prev_playing = True

                # Jitter the sleep by about 15% so many clients that started at
                # the same second don't stay in lockstep hammering the server
                jitter = poll_rate * random.uniform(-0.15, 0.15)
                time.sleep(max(0.1, poll_rate + jitter))

            except KeyboardInterrupt:
                break

    finally:
        # restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print('')
        print('[OK] Client stopped')
        # send a final pause so the tile clears
        make_request(f'{server_url}?action=update', {
            'username': username,
            'track': '',
            'artist': '',
            'isPlaying': False,
        }, 'POST')


if __name__ == '__main__':
    main()
