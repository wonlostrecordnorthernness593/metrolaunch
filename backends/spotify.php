<?php
/*
 * Spotify Status Server for MetroLaunch
 * ======================================
 * File is on the Leopard main server...
 * 
 * Endpoints
 *   POST ?action=register     — Register a username
 *   POST ?action=update       — Push song status from the client script
 *   GET  ?action=status&username=...  — PWA polls this for current status
 *   GET  ?action=cover&username=...   — Proxies the cached Discogs cover image
 */

define('DISCOGS_KEY', '');
define('DISCOGS_SECRET', '');
define('DATA_FILE', __DIR__ . '/spotify_users.json');

// ── CORS headers ──
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Access-Control-Allow-Private-Network: true');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// ── helpers ──

function load_data(): array {
    if (!file_exists(DATA_FILE)) return [];
    $raw = file_get_contents(DATA_FILE);
    if (!$raw) return [];
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

function save_data(array $data): void {
    file_put_contents(DATA_FILE, json_encode($data, JSON_PRETTY_PRINT), LOCK_EX);
}

function json_response(array $payload, int $code = 200): void {
    http_response_code($code);
    header('Content-Type: application/json');
    header('Cache-Control: no-store, no-cache, must-revalidate');
    echo json_encode($payload);
    exit;
}

function read_post_body(): array {
    $raw = file_get_contents('php://input');
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

/**
 * Search Discogs for album art and return the cover image URL
 */
function fetch_discogs_cover(string $artist, string $track): ?string {
    $query = urlencode("$artist $track");
    $url = "https://api.discogs.com/database/search?q={$query}&type=release";

    $opts = [
        'http' => [
            'method' => 'GET',
            'header' => implode("\r\n", [
                'User-Agent: MetroLaunchIOS/1.0',
                'Authorization: Discogs key=' . DISCOGS_KEY . ', secret=' . DISCOGS_SECRET,
            ]),
            'timeout' => 8,
        ],
        'ssl' => [
            'verify_peer' => false,
            'verify_peer_name' => false,
        ],
    ];
    $ctx = stream_context_create($opts);
    $resp = @file_get_contents($url, false, $ctx);
    if ($resp === false) return null;

    $data = json_decode($resp, true);
    $results = $data['results'] ?? [];
    if (empty($results)) return null;

    $cover = $results[0]['cover_image'] ?? null;
    if ($cover && strpos($cover, 'spacer.gif') === false) {
        return $cover;
    }
    return null;
}

/**
 * Download a remote image and return its raw bytes
 */
function proxy_image(string $url): ?array {
    $opts = [
        'http' => [
            'method' => 'GET',
            'header' => 'User-Agent: MetroLaunchIOS/1.0',
            'timeout' => 8,
        ],
        'ssl' => [
            'verify_peer' => false,
            'verify_peer_name' => false,
        ],
    ];
    $ctx = stream_context_create($opts);
    $img = @file_get_contents($url, false, $ctx);
    if ($img === false) return null;

    // try to detect content type from response headers
    $contentType = 'image/jpeg';
    if (isset($http_response_header)) {
        foreach ($http_response_header as $hdr) {
            if (stripos($hdr, 'Content-Type:') === 0) {
                $contentType = trim(substr($hdr, 13));
                break;
            }
        }
    }
    return ['data' => $img, 'type' => $contentType];
}

// ── routing ──

$action = $_GET['action'] ?? '';

switch ($action) {

    // ── register ──
    case 'register':
        if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
            json_response(['error' => 'POST required'], 405);
        }
        $body = read_post_body();
        $username = trim($body['username'] ?? '');
        if ($username === '') {
            json_response(['error' => 'username is required'], 400);
        }
        // sanitise: alphanumeric + underscores + dashes only
        if (!preg_match('/^[a-zA-Z0-9_-]{1,32}$/', $username)) {
            json_response(['error' => 'Invalid username. Use a-z, 0-9, _ or - (max 32 chars)'], 400);
        }

        $data = load_data();
        $existed = isset($data[$username]);
        if (!$existed) {
            $data[$username] = [
                'track'     => '',
                'artist'    => '',
                'isPlaying' => false,
                'coverUrl'  => null,
                'updatedAt' => time(),
            ];
            save_data($data);
        }
        json_response([
            'ok'       => true,
            'created'  => !$existed,
            'username' => $username,
        ]);
        break;

    // ── update ──
    case 'update':
        if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
            json_response(['error' => 'POST required'], 405);
        }
        $body = read_post_body();
        $username  = trim($body['username'] ?? '');
        $track     = trim($body['track'] ?? '');
        $artist    = trim($body['artist'] ?? '');
        $isPlaying = !empty($body['isPlaying']);

        if ($username === '') {
            json_response(['error' => 'username is required'], 400);
        }

        $data = load_data();
        if (!isset($data[$username])) {
            json_response(['error' => 'Unknown username. Register first.'], 404);
        }

        $prev = $data[$username];
        $songChanged = ($prev['track'] !== $track || $prev['artist'] !== $artist);

        // fetch new cover art from Discogs when the song changes
        $coverUrl = $prev['coverUrl'];
        if ($isPlaying && $songChanged && $track !== '' && $artist !== '') {
            $newCover = fetch_discogs_cover($artist, $track);
            $coverUrl = $newCover; // null if not found
        }
        if (!$isPlaying) {
            // keep the last cover url so the tile can still show it briefly
        }

        $data[$username] = [
            'track'     => $track,
            'artist'    => $artist,
            'isPlaying' => $isPlaying,
            'coverUrl'  => $coverUrl,
            'updatedAt' => time(),
        ];
        save_data($data);

        json_response(['ok' => true, 'coverFound' => ($coverUrl !== null)]);
        break;

    // ── status (PWA asks for this) ──
    case 'status':
        $username = trim($_GET['username'] ?? '');
        if ($username === '') {
            json_response(['error' => 'username is required'], 400);
        }

        $data = load_data();
        if (!isset($data[$username])) {
            json_response(['error' => 'Unknown username'], 404);
        }

        $entry = $data[$username];
        $selfUrl = strtok($_SERVER['REQUEST_URI'] ?? '', '?');
        // fall back to script name if REQUEST_URI parsing fails
        if (!$selfUrl) $selfUrl = $_SERVER['SCRIPT_NAME'] ?? 'spotify.php';

        $coverEndpoint = null;
        if ($entry['coverUrl'] && $entry['isPlaying']) {
            $coverEndpoint = $selfUrl . '?action=cover&username=' . urlencode($username) . '&t=' . $entry['updatedAt'];
        }

        json_response([
            'isPlaying' => (bool) $entry['isPlaying'],
            'track'     => $entry['track'],
            'artist'    => $entry['artist'],
            'coverUrl'  => $coverEndpoint,
        ]);
        break;

    // ── cover image proxy ──
    case 'cover':
        $username = trim($_GET['username'] ?? '');
        if ($username === '') {
            http_response_code(400);
            exit('Missing username');
        }

        $data = load_data();
        $entry = $data[$username] ?? null;
        if (!$entry || !$entry['coverUrl']) {
            http_response_code(404);
            exit('No cover art');
        }

        $img = proxy_image($entry['coverUrl']);
        if (!$img) {
            http_response_code(502);
            exit('Failed to fetch cover image');
        }

        header('Content-Type: ' . $img['type']);
        header('Access-Control-Allow-Origin: *');
        header('Cache-Control: public, max-age=86400');
        echo $img['data'];
        exit;

    // ── fallback ──
    default:
        json_response([
            'service' => 'MetroLaunch Spotify Server',
            'version' => '2.0',
            'endpoints' => [
                'POST ?action=register'            => 'Register a username',
                'POST ?action=update'              => 'Push song status',
                'GET  ?action=status&username=...'  => 'Get current status',
                'GET  ?action=cover&username=...'   => 'Get cover art image',
            ],
        ]);
        break;
}
