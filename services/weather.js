/* ================================================================
   METRO LAUNCHER — Weather Service
   ----------------------------------------------------------------
   Owns all networking, caching, polling, and DOM rendering for the
   Weather live tile.
   ================================================================ */

(function () {
  const TILE_ID = '__weather__';
  const CACHE_KEY = 'metro_weather_cache_v2';
  const TTL_MS = 5 * 60 * 1000;
  const AVAILABLE_ICONS = [
    '01d', '01n', '02d', '02n', '03d', '03n', '04d', '04n',
    '09d', '09n', '10d', '10n', '11d', '11n', '13d', '13n',
    '50d', '50n',
  ];

  let deps = null;
  let data = null;
  let loading = false;
  let pollTimer = null;

  function cacheGet() {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      const obj = JSON.parse(raw);
      if (Date.now() - obj.ts > TTL_MS) return null;
      return obj.data;
    } catch { return null; }
  }

  function cacheSet(v) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: v })); } catch { }
  }

  function init(injected) {
    deps = injected;
  }

  function fetchData() {
    const settings = deps.getSettings();
    const zip = settings.weatherZip;

    if (!zip || !settings.weatherApiKey || !settings.weatherCountry) {
      data = null;
      loading = false;
      updateFace();
      return Promise.resolve();
    }

    const cached = cacheGet();
    if (cached && cached._zip === zip) {
      data = cached;
      loading = false;
      updateFace();
      return Promise.resolve();
    }

    // offline - don't attempt the network
    if (!navigator.onLine) {
      loading = false;
      updateFace();
      return Promise.resolve();
    }

    loading = true;
    data = null;
    updateFace();

    const units = settings.weatherUseCelsius ? 'metric' : 'imperial';
    const url = `https://api.openweathermap.org/data/2.5/weather?zip=${encodeURIComponent(zip)},${settings.weatherCountry}&appid=${settings.weatherApiKey}&units=${units}`;

    return fetch(url)
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(d => {
        if (!d.main) return;

        const iconCode = d.weather?.length ? d.weather[0].icon : '01d';
        const mappedIcon = AVAILABLE_ICONS.includes(iconCode) ? iconCode : '01d';

        data = {
          _zip: zip,
          location: d.name || zip,
          temp: `${Math.round(d.main.temp)}\u2009\u00B0${settings.weatherUseCelsius ? 'C' : 'F'}`,
          condition: d.weather?.length ? d.weather[0].main : '',
          bgUrl: `./weather_bg/${mappedIcon}.jpg`,
        };
        loading = false;
        cacheSet(data);
        updateFace();
      })
      .catch(() => {
        data = null;
        loading = false;
        updateFace();
      });
  }

  function updateFace() {
    const escHtml = deps.escHtml;
    const offline = !navigator.onLine;
    document.querySelectorAll('.weather-back-content').forEach(el => {
      if (offline) {
        // while offline the live tile shows nothing rather than a stale reading
        el.innerHTML = '';
      } else if (data) {
        let bgStyle = '';
        if (data.bgUrl) {
          bgStyle = ` style="background-image: url('${escHtml(data.bgUrl)}');"`;
        }
        el.innerHTML =
          `<div class="weather-bg-blur"${bgStyle}></div>` +
          `<div class="weather-location">${escHtml(data.location)}</div>` +
          `<div class="weather-temp">${escHtml(data.temp)}</div>` +
          `<div class="weather-condition">${escHtml(data.condition)}</div>`;
      } else if (loading) {
        el.innerHTML = '<div class="weather-nodata">Loading weather\u2026</div>';
      } else {
        el.innerHTML = '<div class="weather-nodata">Set zip code in tile settings</div>';
      }
    });
  }

  function start() {
    stop();
    const settings = deps.getSettings();
    if (!settings.weatherZip) return;
    fetchData();
    pollTimer = setInterval(() => {
      localStorage.removeItem(CACHE_KEY);
      fetchData();
    }, TTL_MS);
  }

  function stop() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  function purgeCache() {
    localStorage.removeItem(CACHE_KEY);
  }

  function isRunning() {
    return pollTimer !== null;
  }

  window.WeatherService = {
    TILE_ID,
    CACHE_KEY,
    init,
    fetchData,
    updateFace,
    start,
    stop,
    purgeCache,
    isRunning,
    getData: () => data,
    isLoading: () => loading,
  };
})();
