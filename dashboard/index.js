/* ============================================================
   J.A.R.V.I.S. HUD — Dashboard Logic
   Talks to the dashboard backend at the same origin:
     GET  /api/system      — live host stats
     GET  /api/news?type=  — RSS-aggregated headlines
     GET  /api/weather     — current weather
     GET  /api/health      — MCP server reachability
     GET  /api/activity    — recent activity entries
   ============================================================ */

const WEATHER_CITY = 'New York';

const POLL_SYSTEM_MS   = 5000;
const POLL_NEWS_MS     = 5 * 60 * 1000;
const POLL_WEATHER_MS  = 10 * 60 * 1000;
const POLL_HEALTH_MS   = 5000;
const POLL_ACTIVITY_MS = 4000;

// ── Boot Sequence ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initWaveform();

    updateDiagnostics();
    loadNewsFeed();
    loadWeather();
    refreshHealth();
    refreshActivity();

    setInterval(updateDiagnostics, POLL_SYSTEM_MS);
    setInterval(loadNewsFeed,      POLL_NEWS_MS);
    setInterval(loadWeather,       POLL_WEATHER_MS);
    setInterval(refreshHealth,     POLL_HEALTH_MS);
    setInterval(refreshActivity,   POLL_ACTIVITY_MS);
    setInterval(updateWaveformIdle, 200);

    addLog('System boot sequence initiated.');
    addLog('Polling MCP-backed APIs for live data.');
});


// ── Clock ────────────────────────────────────────────────────

function initClock() {
    updateClock();
    setInterval(updateClock, 1000);
}

function updateClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', {
        hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
    const dateStr = now.toLocaleDateString('en-US', {
        weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
    }).toUpperCase();
    document.getElementById('time-display').textContent = timeStr;
    document.getElementById('date-display').textContent = dateStr;
}


// ── Waveform Visualizer ──────────────────────────────────────

const WAVE_BARS = 24;
let waveActive = false;

function initWaveform() {
    const container = document.getElementById('waveform');
    container.innerHTML = '';
    for (let i = 0; i < WAVE_BARS; i++) {
        const bar = document.createElement('div');
        bar.className = 'wave-bar';
        bar.style.height = '4px';
        container.appendChild(bar);
    }
}

function updateWaveformIdle() {
    if (waveActive) return;
    const bars = document.querySelectorAll('.wave-bar');
    bars.forEach((bar, i) => {
        const h = 3 + Math.sin(Date.now() / 500 + i * 0.5) * 3;
        bar.style.height = `${h}px`;
        bar.style.opacity = '0.4';
    });
}

function activateWaveform() {
    waveActive = true;
    const label = document.querySelector('.voice-label');
    label.textContent = 'PROCESSING';
    label.style.color = 'var(--arc-glow)';

    const interval = setInterval(() => {
        if (!waveActive) { clearInterval(interval); return; }
        const bars = document.querySelectorAll('.wave-bar');
        bars.forEach((bar) => {
            const h = 5 + Math.random() * 45;
            bar.style.height = `${h}px`;
            bar.style.opacity = '0.9';
        });
    }, 100);

    setTimeout(() => {
        waveActive = false;
        const label = document.querySelector('.voice-label');
        label.textContent = 'AWAITING INPUT';
        label.style.color = '';
    }, 4000);
}


// ── Diagnostics (real /api/system) ───────────────────────────

async function updateDiagnostics() {
    try {
        const res = await fetch('/api/system');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d = await res.json();

        animateBar('cpu-bar',  d.cpu_percent);
        animateBar('mem-bar',  d.ram_percent);
        animateBar('disk-bar', d.disk_percent);
        animateBar('net-bar',  70);

        document.getElementById('cpu-value').textContent  = `${Math.round(d.cpu_percent)}%`;
        document.getElementById('mem-value').textContent  = `${Math.round(d.ram_percent)}%`;
        document.getElementById('disk-value').textContent = `${Math.round(d.disk_percent)}%`;
        document.getElementById('net-value').textContent  = 'ACTIVE';
    } catch (e) {
        document.getElementById('net-value').textContent = 'OFFLINE';
    }
}

function animateBar(id, value) {
    const bar = document.getElementById(id);
    if (bar) bar.style.width = `${value}%`;
}


// ── News Feed (real /api/news) ───────────────────────────────

function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s ?? '';
    return div.innerHTML;
}

function relativeTime(isoDate) {
    if (!isoDate) return 'LIVE';
    const t = Date.parse(isoDate);
    if (isNaN(t)) return 'LIVE';
    const diff = Date.now() - t;
    const m = Math.round(diff / 60000);
    if (m < 1) return 'JUST NOW';
    if (m < 60) return `${m} MIN AGO`;
    const h = Math.round(m / 60);
    if (h < 24) return `${h} HR AGO`;
    const d = Math.round(h / 24);
    return `${d} DAY${d === 1 ? '' : 'S'} AGO`;
}

async function loadNewsFeed() {
    try {
        const res = await fetch('/api/news?type=world');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderNewsFeed(data.articles || []);
    } catch (e) {
        const container = document.getElementById('news-feed');
        container.innerHTML = `
            <div class="news-item">
                <span class="news-source">[!]</span>
                <span class="news-title">News feed unreachable.</span>
                <span class="news-time">OFFLINE</span>
            </div>`;
    }
}

function renderNewsFeed(articles) {
    const container = document.getElementById('news-feed');
    container.innerHTML = '';

    if (articles.length === 0) {
        container.innerHTML = `
            <div class="news-item">
                <span class="news-source">[—]</span>
                <span class="news-title">No headlines available.</span>
                <span class="news-time">—</span>
            </div>`;
        return;
    }

    articles.slice(0, 8).forEach((item, i) => {
        const el = document.createElement('div');
        el.className = 'news-item';
        el.style.animationDelay = `${i * 0.1}s`;
        el.innerHTML = `
            <span class="news-source">[${escapeHtml(item.source)}]</span>
            <span class="news-title">${escapeHtml(item.title)}</span>
            <span class="news-time">${escapeHtml(relativeTime(item.published))}</span>
        `;
        container.appendChild(el);
    });
}


// ── Weather (real /api/weather) ──────────────────────────────

async function loadWeather() {
    try {
        const url = `/api/weather?city=${encodeURIComponent(WEATHER_CITY)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d = await res.json();

        const temp = d.temperature_f != null ? Math.round(d.temperature_f) : '--';
        const hum  = d.humidity_pct  != null ? Math.round(d.humidity_pct)  : '--';
        const wind = d.wind_mph      != null ? Math.round(d.wind_mph)      : '--';

        document.getElementById('weather-temp').textContent      = `${temp}°F`;
        document.getElementById('weather-condition').textContent = (d.condition || '').toUpperCase();
        document.getElementById('weather-humidity').textContent  = `${hum}%`;
        document.getElementById('weather-wind').textContent      = `${wind} MPH`;
        document.getElementById('weather-location').textContent  = (d.city || WEATHER_CITY).toUpperCase();
    } catch (e) {
        document.getElementById('weather-condition').textContent = 'OFFLINE';
    }
}


// ── Health (MCP / dashboard connectivity) ────────────────────

async function refreshHealth() {
    try {
        const res = await fetch('/api/health');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d = await res.json();
        setMcpStatus(d.mcp === 'online');
    } catch (e) {
        setMcpStatus(false);
    }
}

function setMcpStatus(online) {
    const el = document.getElementById('mcp-status');
    if (!el) return;
    el.textContent = online ? '● CONNECTED' : '● OFFLINE';
    el.classList.toggle('online', online);
}


// ── Activity Log (server-side recent + client-side appends) ──

let _lastActivityTs = 0;

async function refreshActivity() {
    try {
        const res = await fetch('/api/activity');
        if (!res.ok) return;
        const data = await res.json();
        const entries = (data.entries || []).filter(e => e.timestamp > _lastActivityTs);
        // Server entries come newest-first; insert oldest-first so newest ends up on top.
        for (let i = entries.length - 1; i >= 0; i--) {
            addLog(entries[i].message, entries[i].timestamp);
            _lastActivityTs = Math.max(_lastActivityTs, entries[i].timestamp);
        }
    } catch (e) { /* ignore */ }
}

function addLog(message, tsMs) {
    const container = document.getElementById('activity-log');
    const now = tsMs ? new Date(tsMs) : new Date();
    const time = now.toLocaleTimeString('en-US', {
        hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
    });

    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-msg">${escapeHtml(message)}</span>
    `;
    container.insertBefore(entry, container.firstChild);

    while (container.children.length > 20) {
        container.removeChild(container.lastChild);
    }
}


// ── Quick Action Buttons ─────────────────────────────────────

async function simulateAction(action) {
    activateWaveform();

    switch (action) {
        case 'news':
            addLog('Refreshing global news briefing...');
            await loadNewsFeed();
            addLog('News briefing updated from live feeds.');
            break;
        case 'weather':
            addLog('Checking weather conditions...');
            await loadWeather();
            addLog(`Weather updated for ${WEATHER_CITY}.`);
            break;
        case 'system':
            addLog('Running system diagnostics...');
            await updateDiagnostics();
            addLog('Diagnostics complete.');
            break;
        case 'search':
            addLog('Web search must be triggered by voice — say "search for ..."');
            break;
    }
}


// ── Easter Egg: Konami Code ──────────────────────────────────

let konamiSequence = [];
const konamiCode = [38, 38, 40, 40, 37, 39, 37, 39, 66, 65];

document.addEventListener('keydown', (e) => {
    konamiSequence.push(e.keyCode);
    if (konamiSequence.length > konamiCode.length) konamiSequence.shift();
    if (JSON.stringify(konamiSequence) === JSON.stringify(konamiCode)) {
        addLog('Easter egg activated. Welcome, Mr. Stark.');
        document.querySelector('.logo-text h1').textContent = 'MARK LXXXV';
        document.querySelector('.logo-text .subtitle').textContent = 'NANOTECH SUIT INTERFACE';
        konamiSequence = [];
    }
});
