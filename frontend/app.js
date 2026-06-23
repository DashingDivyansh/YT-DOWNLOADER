const urlInput = document.getElementById('urlInput');
const fetchBtn = document.getElementById('fetchBtn');
const fetchBtnText = document.getElementById('fetchBtnText');
const fetchSpinner = document.getElementById('fetchSpinner');
const contentArea = document.getElementById('contentArea');
const videoGrid = document.getElementById('videoGrid');
const playlistTitle = document.getElementById('playlistTitle');
const selectionBadge = document.getElementById('selectionBadge');
const selectAllBtn = document.getElementById('selectAllBtn');
const repairBtn = document.getElementById('repairBtn');
const qualitySelect = document.getElementById('qualitySelect');
const concurrentSelect = document.getElementById('concurrentSelect');
const downloadBtn = document.getElementById('downloadBtn');
const toastContainer = document.getElementById('toastContainer');
const overallProgressContainer = document.getElementById('overallProgressContainer');
const overallProgressText = document.getElementById('overallProgressText');
const overallProgressBar = document.getElementById('overallProgressBar');

let currentVideos = [];
let allSelected = false;
let currentPlaylistTitle = null;
let currentType = null;

// ----------------- TOAST NOTIFICATIONS -----------------
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span>${message}</span>
        <button class="toast-close">&times;</button>
    `;
    toastContainer.appendChild(toast);

    toast.querySelector('.toast-close').addEventListener('click', () => {
        toast.style.animation = 'slideOutRight 0.3s forwards';
        setTimeout(() => toast.remove(), 300);
    });

    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.animation = 'slideOutRight 0.3s forwards';
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

// ----------------- FETCH LOGIC -----------------
fetchBtn.addEventListener('click', async () => {
    const url = urlInput.value.trim();
    if (!url) {
        showToast('Please enter a valid YouTube URL.', 'error');
        return;
    }

    setLoading(true);

    try {
        const response = await fetch('/api/fetch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed to fetch video data.');
        }

        const data = await response.json();
        renderData(data);
        showToast(`Successfully fetched ${data.videos.length} video(s)!`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        setLoading(false);
    }
});

function setLoading(isLoading) {
    if (isLoading) {
        fetchBtnText.classList.add('hidden');
        fetchSpinner.classList.remove('hidden');
        fetchBtn.disabled = true;
    } else {
        fetchBtnText.classList.remove('hidden');
        fetchSpinner.classList.add('hidden');
        fetchBtn.disabled = false;
    }
}

// ----------------- RENDER DATA -----------------
function renderData(data) {
    contentArea.classList.remove('hidden');
    videoGrid.innerHTML = '';
    currentType = data.type;
    currentPlaylistTitle = data.type === 'playlist' ? (data.playlist_title || 'Playlist') : null;
    currentVideos = data.videos.map((v, index) => ({
        ...v,
        index: v.index || index + 1,
        selected: false
    }));
    allSelected = false;
    selectAllBtn.textContent = 'Select All';

    // Update Header
    if (data.type === 'playlist') {
        playlistTitle.textContent = currentPlaylistTitle;
        selectAllBtn.classList.remove('hidden');
        repairBtn.classList.remove('hidden');
    } else {
        playlistTitle.textContent = 'Single Video';
        selectAllBtn.classList.add('hidden');
        repairBtn.classList.add('hidden');
    }

    // Populate Qualities
    qualitySelect.innerHTML = '';
    data.qualities.forEach(q => {
        const opt = document.createElement('option');
        opt.value = q;
        opt.textContent = q;
        qualitySelect.appendChild(opt);
    });

    // Render Cards
    currentVideos.forEach((video, index) => {
        const card = document.createElement('div');
        card.className = 'video-card';
        card.dataset.id = video.id;
        
        card.innerHTML = `
            <div class="thumbnail-container">
                <img src="${video.thumbnail}" alt="Thumbnail" class="thumbnail" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'100\\' height=\\'100\\'><rect width=\\'100\\' height=\\'100\\' fill=\\'#333\\'/></svg>'">
                <span class="duration-badge">${video.duration}</span>
            </div>
            <div class="card-content">
                <h3 class="video-title" title="${video.title.replace(/"/g, '&quot;')}">${video.index}. ${video.title}</h3>
                <p class="video-channel">${video.channel}</p>
                <div class="card-footer">
                    <label class="checkbox-container">
                        <input type="checkbox" id="check-${video.id}" data-index="${index}">
                        Select
                    </label>
                </div>
            </div>
            <div id="progress-container-${video.id}" class="progress-container hidden">
                <div class="progress-header">
                    <span class="status-badge waiting" id="status-${video.id}">Waiting</span>
                    <span id="percent-${video.id}">0%</span>
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" id="bar-${video.id}"></div>
                </div>
                <div class="progress-stats">
                    <span id="speed-${video.id}">--</span>
                    <span id="eta-${video.id}">--</span>
                </div>
                <div id="link-container-${video.id}"></div>
            </div>
        `;

        videoGrid.appendChild(card);

        // Checkbox event
        const checkbox = card.querySelector(`#check-${video.id}`);
        checkbox.addEventListener('change', (e) => {
            currentVideos[index].selected = e.target.checked;
            if (e.target.checked) {
                card.classList.add('selected');
            } else {
                card.classList.remove('selected');
            }
            updateBadge();
        });
    });

    // Default select all if single video
    if (data.type === 'video' && currentVideos.length > 0) {
        document.getElementById(`check-${currentVideos[0].id}`).click();
    }

    updateBadge();
}

// ----------------- SELECT ALL -----------------
selectAllBtn.addEventListener('click', () => {
    allSelected = !allSelected;
    selectAllBtn.textContent = allSelected ? 'Deselect All' : 'Select All';
    
    const checkboxes = document.querySelectorAll('.checkbox-container input[type="checkbox"]');
    checkboxes.forEach(cb => {
        if (cb.checked !== allSelected) {
            cb.click();
        }
    });
});

function updateBadge() {
    const selectedCount = currentVideos.filter(v => v.selected).length;
    selectionBadge.textContent = `${selectedCount} / ${currentVideos.length} Selected`;
    downloadBtn.disabled = selectedCount === 0;
    repairBtn.disabled = currentType !== 'playlist' || currentVideos.length === 0;
    if(selectedCount === 0) {
        downloadBtn.style.opacity = '0.5';
        downloadBtn.style.cursor = 'not-allowed';
    } else {
        downloadBtn.style.opacity = '1';
        downloadBtn.style.cursor = 'pointer';
    }
}

// ----------------- DOWNLOAD LOGIC -----------------
let totalDownloads = 0;
let completedDownloads = 0;

downloadBtn.addEventListener('click', async () => {
    await startDownload(false);
});

repairBtn.addEventListener('click', async () => {
    await startDownload(true);
});

function buildFileUrl(filename) {
    return `/api/file/${filename.split('/').map(encodeURIComponent).join('/')}`;
}

async function startDownload(repairMode) {
    const targetVideos = repairMode
        ? currentVideos
        : currentVideos.filter(v => v.selected);
    if (targetVideos.length === 0) return;

    const quality = qualitySelect.value;
    const concurrent = parseInt(concurrentSelect.value, 10);
    const selectedVideos = targetVideos.map(v => v.id);
    const items = targetVideos.map(v => ({
        id: v.id,
        title: v.title,
        index: v.index
    }));

    totalDownloads = selectedVideos.length;
    completedDownloads = 0;

    // Reset UI
    overallProgressContainer.classList.remove('hidden');
    updateOverallProgress();
    
    selectedVideos.forEach(vid => {
        const pContainer = document.getElementById(`progress-container-${vid}`);
        pContainer.classList.remove('hidden');
        
        document.getElementById(`status-${vid}`).className = 'status-badge waiting';
        document.getElementById(`status-${vid}`).textContent = 'Queued';
        document.getElementById(`bar-${vid}`).style.width = '0%';
        document.getElementById(`percent-${vid}`).textContent = '0%';
        document.getElementById(`speed-${vid}`).textContent = '--';
        document.getElementById(`eta-${vid}`).textContent = '--';
        document.getElementById(`link-container-${vid}`).innerHTML = '';
    });

    downloadBtn.disabled = true;
    repairBtn.disabled = true;
    downloadBtn.textContent = repairMode ? 'Repairing...' : 'Starting...';

    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                videos: selectedVideos,
                quality,
                concurrent,
                playlist_title: currentPlaylistTitle,
                items,
                repair: repairMode
            })
        });

        if (!response.ok) throw new Error('Failed to start download.');
        
        const { session_id } = await response.json();
        downloadBtn.textContent = repairMode ? 'Repairing...' : 'Downloading...';
        listenToProgress(session_id);

    } catch (error) {
        showToast(error.message, 'error');
        downloadBtn.disabled = false;
        repairBtn.disabled = currentType !== 'playlist';
        downloadBtn.textContent = 'Download';
        overallProgressContainer.classList.add('hidden');
    }
}

function updateOverallProgress() {
    overallProgressText.textContent = `Completed ${completedDownloads} of ${totalDownloads} videos...`;
    const percent = (completedDownloads / totalDownloads) * 100;
    overallProgressBar.style.width = `${percent}%`;
    if (completedDownloads === totalDownloads && totalDownloads > 0) {
        overallProgressText.textContent = `All ${totalDownloads} videos completed! 🎉`;
    }
}

function listenToProgress(sessionId) {
    const eventSource = new EventSource(`/api/progress/${sessionId}`);

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const { video_id, status, percent, speed, eta, filename, error, skipped } = data;

        const statusBadge = document.getElementById(`status-${video_id}`);
        const bar = document.getElementById(`bar-${video_id}`);
        const percentText = document.getElementById(`percent-${video_id}`);
        const speedText = document.getElementById(`speed-${video_id}`);
        const etaText = document.getElementById(`eta-${video_id}`);
        const linkContainer = document.getElementById(`link-container-${video_id}`);

        if (!statusBadge) return; // Might happen if user re-fetched

        if (status === 'queued') {
            statusBadge.className = 'status-badge waiting';
            statusBadge.textContent = 'Queued';
        } else if (status === 'downloading') {
            statusBadge.className = 'status-badge downloading';
            statusBadge.textContent = 'Downloading';
            bar.style.width = `${percent}%`;
            percentText.textContent = `${percent}%`;
            speedText.textContent = speed;
            etaText.textContent = eta;
        } else if (status === 'done') {
            statusBadge.className = 'status-badge done';
            statusBadge.textContent = 'Done';
            bar.style.width = '100%';
            percentText.textContent = '100%';
            speedText.textContent = 'Complete';
            etaText.textContent = '';
            
            // Add download link
            if (filename) {
                linkContainer.innerHTML = `<a href="${buildFileUrl(filename)}" class="download-link" download>Save File</a>`;
            }

            completedDownloads++;
            updateOverallProgress();
            showToast(skipped ? `Already saved: ${filename}` : `Download finished: ${filename}`, 'success');

        } else if (status === 'error') {
            statusBadge.className = 'status-badge error';
            statusBadge.textContent = 'Error';
            speedText.textContent = error || 'Failed';
            
            completedDownloads++; // Count as processed so overall progress completes
            updateOverallProgress();
            showToast(`Error downloading a video.`, 'error');
        }
    };

    eventSource.addEventListener('close', () => {
        eventSource.close();
        downloadBtn.disabled = false;
        repairBtn.disabled = currentType !== 'playlist';
        downloadBtn.textContent = 'Download';
        showToast('All tasks finished!', 'success');
    });

    eventSource.onerror = () => {
        eventSource.close();
        downloadBtn.disabled = false;
        repairBtn.disabled = currentType !== 'playlist';
        downloadBtn.textContent = 'Download';
    };
}
