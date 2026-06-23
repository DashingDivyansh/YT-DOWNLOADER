/* ============================================================
   YT DOWNLOADER PRO — app.js
   Connects to FastAPI backend: /api/fetch, /api/download, /api/progress
   Handles: metadata rendering, selection, quality, concurrency,
            SSE live progress, repair mode, skipped/done/error states
   ============================================================ */

'use strict';

// ============================================================
// DOM REFS
// ============================================================
const $ = id => document.getElementById(id);

const urlInput                = $('urlInput');
const fetchBtn                = $('fetchBtn');
const fetchBtnText            = $('fetchBtnText');
const fetchSpinner            = $('fetchSpinner');
const contentArea             = $('contentArea');
const videoGrid               = $('videoGrid');
const playlistTitle           = $('playlistTitle');
const typeTag                 = $('typeTag');
const selectionBadge          = $('selectionBadge');
const selectAllBtn            = $('selectAllBtn');
const repairBtn               = $('repairBtn');
const qualitySelect           = $('qualitySelect');
const concurrentSlider        = $('concurrentSlider');
const concurrentSelect        = $('concurrentSelect');
const concurrentValue         = $('concurrentValue');
const downloadBtn             = $('downloadBtn');
const toastContainer          = $('toastContainer');
const overallProgressContainer = $('overallProgressContainer');
const overallProgressText     = $('overallProgressText');
const overallProgressBar      = $('overallProgressBar');
const overallPercent          = $('overallPercent');

// ============================================================
// STATE
// ============================================================
let currentVideos       = [];    // array of { id, title, thumbnail, duration, channel, index, selected }
let currentType         = null;  // 'video' | 'playlist'
let currentPlaylistTitle = null;
let allSelected         = false;
let totalDownloads      = 0;
let completedDownloads  = 0;

// ============================================================
// CONCURRENCY SLIDER SYNC
// ============================================================
function updateSliderBackground() {
    const val = concurrentSlider.value;
    const pct = ((val - 1) / 4) * 100;
    concurrentSlider.style.setProperty('--val', `${pct}%`);
    concurrentValue.textContent = `${val}×`;
    // Keep hidden select in sync for form submission
    concurrentSelect.value = val;
}

concurrentSlider.addEventListener('input', updateSliderBackground);
updateSliderBackground(); // Init

// Allow pressing Enter on URL input to trigger fetch
urlInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') fetchBtn.click();
});

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
const TOAST_ICONS = { success: '✅', error: '❌', info: 'ℹ️' };

function showToast(message, type = 'info', duration = 4500) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${TOAST_ICONS[type] || '🔔'}</span>
        <span class="toast-body">${message}</span>
        <button class="toast-close" aria-label="Dismiss">&times;</button>
    `;

    const close = () => {
        toast.style.animation = 'toast-out 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    };

    toast.querySelector('.toast-close').addEventListener('click', close);
    toastContainer.appendChild(toast);
    setTimeout(close, duration);
}

// ============================================================
// LOADING STATE
// ============================================================
function setFetchLoading(loading) {
    if (loading) {
        fetchBtnText.classList.add('hidden');
        fetchSpinner.classList.remove('hidden');
        fetchBtn.disabled = true;
    } else {
        fetchBtnText.classList.remove('hidden');
        fetchSpinner.classList.add('hidden');
        fetchBtn.disabled = false;
    }
}

// ============================================================
// SKELETON CARDS (while fetching)
// ============================================================
function showSkeletons(count = 6) {
    videoGrid.innerHTML = '';
    contentArea.classList.remove('hidden');
    for (let i = 0; i < Math.min(count, 6); i++) {
        const sk = document.createElement('div');
        sk.className = 'skeleton-card';
        sk.innerHTML = `
            <div class="skeleton-thumb skeleton"></div>
            <div class="skeleton-body">
                <div class="skeleton-line skeleton"></div>
                <div class="skeleton-line short skeleton"></div>
            </div>
        `;
        sk.style.animationDelay = `${i * 0.07}s`;
        videoGrid.appendChild(sk);
    }
}

// ============================================================
// FETCH METADATA
// ============================================================
fetchBtn.addEventListener('click', async () => {
    const url = urlInput.value.trim();
    if (!url) {
        showToast('Please paste a YouTube URL first.', 'error');
        urlInput.focus();
        return;
    }

    setFetchLoading(true);
    showSkeletons();
    overallProgressContainer.classList.add('hidden');

    try {
        const res = await fetch('/api/fetch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Server error ${res.status}`);
        }

        const data = await res.json();
        renderData(data);
        showToast(`Fetched ${data.videos.length} video${data.videos.length !== 1 ? 's' : ''}!`, 'success');
    } catch (err) {
        showToast(err.message, 'error');
        videoGrid.innerHTML = '';
        contentArea.classList.add('hidden');
    } finally {
        setFetchLoading(false);
    }
});

// ============================================================
// RENDER METADATA
// ============================================================
function renderData(data) {
    currentType         = data.type;
    currentPlaylistTitle = data.type === 'playlist' ? (data.playlist_title || 'Playlist') : null;
    allSelected         = false;

    currentVideos = data.videos.map((v, i) => ({
        ...v,
        index: v.index ?? i + 1,
        selected: false
    }));

    // Header
    contentArea.classList.remove('hidden');
    if (data.type === 'playlist') {
        typeTag.textContent = 'PLAYLIST';
        typeTag.className = 'type-tag playlist';
        playlistTitle.textContent = currentPlaylistTitle;
        selectAllBtn.classList.remove('hidden');
        repairBtn.classList.remove('hidden');
    } else {
        typeTag.textContent = 'VIDEO';
        typeTag.className = 'type-tag';
        playlistTitle.textContent = currentVideos[0]?.title || 'Single Video';
        selectAllBtn.classList.add('hidden');
        repairBtn.classList.add('hidden');
    }

    // Populate quality dropdown
    qualitySelect.innerHTML = '';
    (data.qualities || []).forEach(q => {
        const opt = document.createElement('option');
        opt.value = q;
        opt.textContent = q;
        qualitySelect.appendChild(opt);
    });

    // Render cards
    videoGrid.innerHTML = '';
    currentVideos.forEach((video, idx) => {
        videoGrid.appendChild(buildVideoCard(video, idx));
    });

    // Auto-select for single video
    if (data.type === 'video' && currentVideos.length > 0) {
        toggleVideoSelection(0, true);
    }

    updateBadge();
}

// ============================================================
// BUILD VIDEO CARD
// ============================================================
function buildVideoCard(video, idx) {
    const card = document.createElement('div');
    card.className = 'video-card';
    card.setAttribute('role', 'listitem');
    card.dataset.id = video.id;
    card.dataset.idx = idx;
    card.style.animationDelay = `${Math.min(idx * 0.05, 0.5)}s`;

    const thumbSrc = video.thumbnail || `https://i.ytimg.com/vi/${video.id}/hqdefault.jpg`;

    card.innerHTML = `
        <div class="thumbnail-wrap">
            <img
                src="${thumbSrc}"
                alt="Thumbnail for ${escapeHtml(video.title)}"
                class="video-thumb"
                loading="lazy"
                onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'320\\' height=\\'180\\'%3E%3Crect width=\\'320\\' height=\\'180\\' fill=\\'%23111827\\'/%3E%3Ctext x=\\'50%25\\' y=\\'50%25\\' dominant-baseline=\\'middle\\' text-anchor=\\'middle\\' fill=\\'%236b7280\\' font-size=\\'13\\' font-family=\\'sans-serif\\'%3ENo thumbnail%3C/text%3E%3C/svg%3E'"
            />
            <div class="thumb-overlay"></div>
            <span class="duration-pill">${video.duration || '—'}</span>
            <span class="index-badge">#${video.index}</span>
            <div class="card-overlay">
                <div class="check-tick">✓</div>
            </div>
        </div>
        <div class="card-body">
            <h3 class="video-title" title="${escapeHtml(video.title)}">${escapeHtml(video.title)}</h3>
            <p class="video-channel">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                ${escapeHtml(video.channel || 'Unknown Channel')}
            </p>
        </div>
        <div class="card-footer">
            <label class="checkbox-label" for="check-${video.id}">
                <span class="custom-checkbox">
                    <input type="checkbox" id="check-${video.id}" data-idx="${idx}" aria-label="Select ${escapeHtml(video.title)}">
                    <span class="checkmark"></span>
                </span>
                Select video
            </label>
        </div>
        <div id="progress-${video.id}" class="card-progress">
            <div class="progress-row">
                <span id="chip-${video.id}" class="status-chip queued">Queued</span>
                <span id="pct-${video.id}"  class="percent-text">0%</span>
            </div>
            <div class="progress-track">
                <div id="bar-${video.id}" class="progress-fill shimmer"></div>
            </div>
            <div class="progress-stats">
                <span id="speed-${video.id}">—</span>
                <span id="eta-${video.id}">—</span>
            </div>
            <div id="link-${video.id}"></div>
        </div>
    `;

    // Click the card body (not checkbox) to toggle
    card.querySelector('.card-body').addEventListener('click', () => {
        const cb = card.querySelector(`#check-${video.id}`);
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event('change', { bubbles: true }));
    });
    card.querySelector('.thumbnail-wrap').addEventListener('click', () => {
        const cb = card.querySelector(`#check-${video.id}`);
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event('change', { bubbles: true }));
    });

    card.querySelector(`#check-${video.id}`).addEventListener('change', e => {
        toggleVideoSelection(idx, e.target.checked);
    });

    return card;
}

// ============================================================
// SELECTION HELPERS
// ============================================================
function toggleVideoSelection(idx, checked) {
    currentVideos[idx].selected = checked;
    const card = videoGrid.querySelector(`[data-id="${currentVideos[idx].id}"]`);
    if (!card) return;
    card.classList.toggle('selected', checked);
    const cb = card.querySelector(`#check-${currentVideos[idx].id}`);
    if (cb) cb.checked = checked;
    updateBadge();
}

selectAllBtn.addEventListener('click', () => {
    allSelected = !allSelected;
    selectAllBtn.textContent = allSelected ? 'Deselect All' : 'Select All';
    selectAllBtn.innerHTML = allSelected
        ? `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg> Deselect All`
        : `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg> Select All`;
    currentVideos.forEach((_, i) => toggleVideoSelection(i, allSelected));
});

function updateBadge() {
    const sel = currentVideos.filter(v => v.selected).length;
    selectionBadge.textContent = `${sel} / ${currentVideos.length} selected`;
    downloadBtn.disabled = sel === 0;
}

// ============================================================
// FILE URL BUILDER
// ============================================================
function buildFileUrl(filename) {
    return `/api/file/${filename.split('/').map(encodeURIComponent).join('/')}`;
}

// ============================================================
// DOWNLOAD
// ============================================================
downloadBtn.addEventListener('click', () => startDownload(false));
repairBtn.addEventListener('click',   () => startDownload(true));

async function startDownload(repairMode) {
    const targets = repairMode
        ? currentVideos
        : currentVideos.filter(v => v.selected);

    if (targets.length === 0) {
        showToast('Please select at least one video.', 'error');
        return;
    }

    const quality    = qualitySelect.value;
    const concurrent = parseInt(concurrentSelect.value, 10);

    totalDownloads    = targets.length;
    completedDownloads = 0;

    // Show overall progress
    overallProgressContainer.classList.remove('hidden');
    updateOverallProgress();

    // Reset per-video UI
    targets.forEach(v => {
        const prog = $(`progress-${v.id}`);
        if (prog) prog.classList.add('visible');
        setChip(v.id, 'queued', 'Queued');
        setBar(v.id, 0, 'shimmer');
        setText(`pct-${v.id}`,   '0%');
        setText(`speed-${v.id}`, '—');
        setText(`eta-${v.id}`,   '—');
        const link = $(`link-${v.id}`);
        if (link) link.innerHTML = '';
    });

    // Disable buttons during download
    downloadBtn.disabled = true;
    repairBtn.disabled   = true;
    downloadBtn.innerHTML = repairMode
        ? `<span class="btn-spinner"></span> Repairing…`
        : `<span class="btn-spinner"></span> Downloading…`;

    try {
        const res = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                videos:         targets.map(v => v.id),
                quality,
                concurrent,
                playlist_title: currentPlaylistTitle,
                items:          targets.map(v => ({ id: v.id, title: v.title, index: v.index })),
                repair:         repairMode
            })
        });

        if (!res.ok) throw new Error('Failed to start download session.');

        const { session_id } = await res.json();
        listenToProgress(session_id);

    } catch (err) {
        showToast(err.message, 'error');
        resetDownloadBtn();
    }
}

function resetDownloadBtn() {
    downloadBtn.disabled = currentVideos.filter(v => v.selected).length === 0;
    repairBtn.disabled   = currentType !== 'playlist';
    downloadBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Download
    `;
}

// ============================================================
// OVERALL PROGRESS
// ============================================================
function updateOverallProgress() {
    const pct = totalDownloads > 0 ? Math.round((completedDownloads / totalDownloads) * 100) : 0;
    overallProgressBar.style.width = `${pct}%`;
    overallPercent.textContent = `${pct}%`;

    if (completedDownloads >= totalDownloads && totalDownloads > 0) {
        overallProgressText.textContent = `🎉 All ${totalDownloads} video${totalDownloads !== 1 ? 's' : ''} done!`;
    } else {
        overallProgressText.textContent = `Downloading ${completedDownloads} of ${totalDownloads} complete…`;
    }
}

// ============================================================
// SSE — LIVE PROGRESS
// ============================================================
function listenToProgress(sessionId) {
    const evtSrc = new EventSource(`/api/progress/${sessionId}`);

    evtSrc.onmessage = e => {
        let data;
        try { data = JSON.parse(e.data); } catch { return; }

        const { video_id, status, percent, speed, eta, filename, error, skipped } = data;

        if (!$(`chip-${video_id}`)) return; // safety check

        switch (status) {
            case 'queued':
                setChip(video_id, 'queued', 'Queued');
                break;

            case 'downloading':
                setChip(video_id, 'downloading', 'Downloading');
                setBar(video_id, percent ?? 0, 'shimmer');
                setText(`pct-${video_id}`,   `${percent ?? 0}%`);
                setText(`speed-${video_id}`, speed || '—');
                setText(`eta-${video_id}`,   eta   || '—');
                break;

            case 'done':
                setChip(video_id, skipped ? 'skipped' : 'done', skipped ? 'Skipped' : 'Done ✓');
                setBar(video_id, 100, 'done');
                setText(`pct-${video_id}`,   '100%');
                setText(`speed-${video_id}`, skipped ? 'Already saved' : 'Complete');
                setText(`eta-${video_id}`,   '');

                if (filename) {
                    const linkEl = $(`link-${video_id}`);
                    if (linkEl) {
                        linkEl.innerHTML = `
                            <a href="${buildFileUrl(filename)}"
                               class="download-link-btn"
                               download="${escapeHtml(filename.split('/').pop())}">
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                                Save File
                            </a>`;
                    }
                }

                completedDownloads++;
                updateOverallProgress();
                showToast(
                    skipped
                        ? `Already saved: ${filename || video_id}`
                        : `Downloaded: ${(filename || video_id).split('/').pop()}`,
                    skipped ? 'info' : 'success',
                    3500
                );
                break;

            case 'error':
                setChip(video_id, 'error', 'Error ✗');
                setBar(video_id, 100, 'error');
                setText(`speed-${video_id}`, error ? truncate(error, 40) : 'Failed');

                completedDownloads++;
                updateOverallProgress();
                showToast(`Failed: ${truncate(error || 'Unknown error', 60)}`, 'error', 6000);
                break;
        }
    };

    evtSrc.addEventListener('close', () => {
        evtSrc.close();
        resetDownloadBtn();
        if (completedDownloads >= totalDownloads) {
            showToast('All tasks finished!', 'success');
        }
    });

    evtSrc.onerror = () => {
        evtSrc.close();
        resetDownloadBtn();
    };
}

// ============================================================
// DOM HELPERS
// ============================================================
function setChip(videoId, cssClass, label) {
    const el = $(`chip-${videoId}`);
    if (!el) return;
    el.className = `status-chip ${cssClass}`;
    el.textContent = label;
}

function setBar(videoId, pct, state) {
    const el = $(`bar-${videoId}`);
    if (!el) return;
    el.style.width = `${Math.min(pct, 100)}%`;
    el.className = 'progress-fill' + (state ? ` ${state}` : '');
}

function setText(id, val) {
    const el = $(id);
    if (el) el.textContent = val;
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function truncate(str, max) {
    return str.length > max ? str.slice(0, max) + '…' : str;
}
