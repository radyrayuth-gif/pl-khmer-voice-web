/**
 * PL Khmer Voice Web Studio - Master Application Controller
 * Replicates the exact behavior, 9-column table, Auto-Start pipeline, and audio player of main.py.
 */

class AppState {
    constructor() {
        this.items = [];
        this.currentFilename = "untitled.srt";
        this.settings = {
            apiKeys: [],
            modelName: "gemini-3.5-flash-lite",
            style: "emotion_acting",
            batchSize: 30,
            concurrency: 8,
            requestDelay: 0.1,
            rate: "+20%",
            pitch: "+0Hz",
            bitrate: "128k"
        };
        this.fileLibrary = []; // Array of { filename, items, masterAudioUrl }
        this.currentFileIndex = 0;
        this.isPipelineRunning = false;
        this.activeRowPlayingId = null;
        this.masterAudioUrl = null;
        this.ws = null;
    }
}

const state = new AppState();

// DOM References
const dom = {
    // Header & Status
    serverStatusPill: document.getElementById("serverStatusPill"),
    statusPillText: document.getElementById("statusPillText"),
    activeModelLabel: document.getElementById("activeModelLabel"),
    btnLoadSample: document.getElementById("btnLoadSample"),
    btnOpenSettings: document.getElementById("btnOpenSettings"),
    mainModelSelect: document.getElementById("mainModelSelect"),
    mainStyleSelect: document.getElementById("mainStyleSelect"),

    // File Toolbar
    filePathDisplay: document.getElementById("filePathDisplay"),
    multiFileDropdown: document.getElementById("multiFileDropdown"),
    srtFileInput: document.getElementById("srtFileInput"),
    btnMasterAction: document.getElementById("btnMasterAction"),
    btnMasterActionText: document.getElementById("btnMasterActionText"),
    btnAnalyzeGenders: document.getElementById("btnAnalyzeGenders"),
    btnStartTranslation: document.getElementById("btnStartTranslation"),
    btnGenAllVoices: document.getElementById("btnGenAllVoices"),
    btnExportMaster: document.getElementById("btnExportMaster"),

    // Teleprompter Banner (matching #teleprompterFrame)
    teleprompterFrame: document.getElementById("teleprompterFrame"),
    teleprompterSpinner: document.getElementById("teleprompterSpinner"),
    teleprompterStatusText: document.getElementById("teleprompterStatusText"),
    teleprompterPct: document.getElementById("teleprompterPct"),
    teleprompterProgressBar: document.getElementById("teleprompterProgressBar"),

    // Filter & Stats
    statTotalCount: document.getElementById("statTotalCount"),
    statTransCount: document.getElementById("statTransCount"),
    statAudioCount: document.getElementById("statAudioCount"),
    statRemainingCount: document.getElementById("statRemainingCount"),
    progressStatusLabel: document.getElementById("progressStatusLabel"),
    fileInfoLabel: document.getElementById("fileInfoLabel"),
    progressBarText: document.getElementById("progressBarText"),
    tableFilterInput: document.getElementById("tableFilterInput"),

    // Table
    tableBody: document.getElementById("tableBody"),

    // Master Player
    masterAudioElement: document.getElementById("masterAudioElement"),
    rowAudioElement: document.getElementById("rowAudioElement"),
    btnMasterPlayPause: document.getElementById("btnMasterPlayPause"),
    playerIconPlay: document.getElementById("playerIconPlay"),
    playerIconPause: document.getElementById("playerIconPause"),
    masterTrackTitle: document.getElementById("masterTrackTitle"),
    playerCurrentTime: document.getElementById("playerCurrentTime"),
    playerTotalDuration: document.getElementById("playerTotalDuration"),
    masterTimelineSlider: document.getElementById("masterTimelineSlider"),
    autoScrollToggle: document.getElementById("autoScrollToggle"),
    masterVolumeSlider: document.getElementById("masterVolumeSlider"),
    btnDownloadMaster: document.getElementById("btnDownloadMaster"),

    // Settings Modal
    settingsModal: document.getElementById("settingsModal"),
    btnCloseSettings: document.getElementById("btnCloseSettings"),
    btnCancelSettings: document.getElementById("btnCancelSettings"),
    btnSaveSettings: document.getElementById("btnSaveSettings"),
    settingsApiKeys: document.getElementById("settingsApiKeys"),
    btnToggleKeyVisibility: document.getElementById("btnToggleKeyVisibility"),
    btnTestKey: document.getElementById("btnTestKey"),
    testKeySpinner: document.getElementById("testKeySpinner"),
    keyTestResult: document.getElementById("keyTestResult"),
    settingsModel: document.getElementById("settingsModel"),
    settingsStyle: document.getElementById("settingsStyle"),
    settingsRateSlider: document.getElementById("settingsRateSlider"),
    labelRateVal: document.getElementById("labelRateVal"),
    settingsPitchSlider: document.getElementById("settingsPitchSlider"),
    labelPitchVal: document.getElementById("labelPitchVal"),
    settingsBatchSlider: document.getElementById("settingsBatchSlider"),
    labelBatchSize: document.getElementById("labelBatchSize"),
    settingsConcurrencySlider: document.getElementById("settingsConcurrencySlider"),
    labelConcurrency: document.getElementById("labelConcurrency"),
    settingsBitrate: document.getElementById("settingsBitrate"),

    toastContainer: document.getElementById("toastContainer")
};

// Toast Notifications
function showToast(message, type = "info", duration = 4000) {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    const icon = type === "success" ? "✅" : (type === "error" ? "❌" : "ℹ️");
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    dom.toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function formatTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

// WebSocket Setup
function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/progress`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        dom.serverStatusPill.querySelector(".status-dot").className = "status-dot green";
        dom.statusPillText.textContent = "Server Online";
        // Cloud Keep-Alive: Ping server every 20s so Render proxy never drops connection
        if (state.pingInterval) clearInterval(state.pingInterval);
        state.pingInterval = setInterval(() => {
            if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                state.ws.send(JSON.stringify({ type: "ping" }));
            }
        }, 20000);
    };

    state.ws.onclose = () => {
        if (state.pingInterval) clearInterval(state.pingInterval);
        dom.serverStatusPill.querySelector(".status-dot").className = "status-dot red";
        dom.statusPillText.textContent = "Disconnected";
        setTimeout(initWebSocket, 3000);
    };

    state.ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === "pong") return; // Heartbeat reply
            handleWsMessage(data);
        } catch (e) {}
    };
}

function handleWsMessage(data) {
    switch (data.type) {
        case "pipeline_status":
            handlePipelineStatus(data);
            break;
        case "gender_update":
            dom.teleprompterStatusText.textContent = data.message;
            break;
        case "row_updated":
            handleRowUpdated(data);
            break;
    }
}

function handlePipelineStatus(data) {
    const msg = data.message || "កំពុងដំណើរការ...";
    dom.teleprompterStatusText.textContent = msg;
    if (dom.progressStatusLabel) dom.progressStatusLabel.textContent = msg;
    const pct = `${data.progress || 0}%`;
    dom.teleprompterPct.textContent = pct;
    dom.teleprompterProgressBar.style.width = pct;
    if (dom.progressBarText) dom.progressBarText.textContent = pct;

    if (data.stage === "diarization" || data.stage === "translating_and_dubbing" || data.stage === "finishing_tts" || data.stage === "compiling_master") {
        state.isPipelineRunning = true;
        dom.teleprompterSpinner.style.display = "inline-block";
        dom.btnMasterAction.classList.add("running");
        dom.btnMasterActionText.textContent = "Stop / បញ្ឈប់";
    } else {
        state.isPipelineRunning = false;
        dom.teleprompterSpinner.style.display = "none";
        dom.btnMasterAction.classList.remove("running");
        dom.btnMasterActionText.textContent = "Auto Start";
        if (data.stage === "completed") {
            showToast(data.message || "ដំណើរការបានបញ្ចប់ដោយជោគជ័យ!", "success");
            if (data.master_url) {
                const originalBaseName = (state.currentFilename || "master_voiceover").replace(/\.[^/.]+$/, "");
                const mp3FileName = originalBaseName + ".mp3";

                state.masterAudioUrl = data.master_url;
                dom.masterAudioElement.src = data.master_url;
                dom.btnDownloadMaster.href = data.master_url;
                dom.btnDownloadMaster.download = mp3FileName;
                dom.btnDownloadMaster.style.display = "inline-flex";
                dom.masterTrackTitle.textContent = mp3FileName;

                // Automatically trigger MP3 download with exact original file name
                const aDl = document.createElement("a");
                aDl.href = data.master_url;
                aDl.download = mp3FileName;
                document.body.appendChild(aDl);
                aDl.click();
                aDl.remove();
                showToast(`⬇️ បាន Export & Download ឯកសារ ${mp3FileName} ដោយជោគជ័យ!`, "success");
            }
        } else if (data.stage === "error") {
            showToast(data.message, "error");
        }
    }
}

function handleRowUpdated(data) {
    const item = state.items.find(it => it.id === data.id);
    if (!item) return;

    if (data.khmer_text !== undefined) item.khmer_text = data.khmer_text;
    if (data.gender !== undefined) item.gender = data.gender;
    if (data.voice !== undefined) item.voice = data.voice;
    if (data.audio_url !== undefined) item.audio_url = data.audio_url;
    if (data.duration_ms !== undefined) item.duration_ms = data.duration_ms;
    if (data.duration_str !== undefined) item.duration_str = data.duration_str;
    if (data.speed !== undefined) item.speed = data.speed;
    if (data.status !== undefined) item.status = data.status;

    updateTableRow(item);
    updateSummaryStats();
}

// Subtitle Table Rendering (Exact 9 Columns)
function renderTable() {
    if (!state.items || state.items.length === 0) {
        dom.tableBody.innerHTML = `
            <tr class="empty-row">
                <td colspan="9">
                    <div class="empty-state">
                        <div class="empty-icon">📂</div>
                        <h3>មិនទាន់មានឯកសារ Subtitle ឡើយ</h3>
                        <p>សូមចុចប៊ូតុង <strong>📂 រើស SRT</strong> ដើម្បីជ្រើសរើសឯកសារ SRT របស់អ្នក។</p>
                    </div>
                </td>
            </tr>
        `;
        updateSummaryStats();
        return;
    }

    const searchQuery = dom.tableFilterInput.value.trim().toLowerCase();
    const rowsHtml = state.items.map(item => {
        if (searchQuery) {
            const matchId = String(item.id).includes(searchQuery);
            const matchOrig = (item.orig_text || "").toLowerCase().includes(searchQuery);
            const matchKhmer = (item.khmer_text || "").toLowerCase().includes(searchQuery);
            if (!matchId && !matchOrig && !matchKhmer) return "";
        }

        const hasAudio = !!item.audio_url;
        const isEcho = item.echo === "Yes";
        const statusClass = getStatusClass(item.status);

        return `
            <tr id="row-${item.id}" data-id="${item.id}">
                <td class="sub-idx">${item.id}</td>
                <td>
                    <span class="timing-box">${item.time_str}</span>
                </td>
                <td>
                    <select class="table-select row-voice-select" data-id="${item.id}">
                        <option value="Auto" ${item.voice === "Auto" ? "selected" : ""}>ស្វ័យប្រវត្តិតាមភេទ (Auto)</option>
                        <option value="Sreymom" ${item.voice === "Sreymom" ? "selected" : ""}>ស្រីម៉ុម - Sreymom (ស្រី)</option>
                        <option value="Piseth" ${item.voice === "Piseth" ? "selected" : ""}>ពិសិដ្ឋ - Piseth (ប្រុស)</option>
                    </select>
                </td>
                <td style="text-align: center;">
                    <input type="checkbox" class="echo-checkbox" data-id="${item.id}" ${isEcho ? "checked" : ""} title="បើក/បិទ សំឡេង Echo">
                </td>
                <td>
                    <div class="orig-text-cell">${escapeHtml(item.orig_text)}</div>
                </td>
                <td>
                    <textarea class="khmer-input-cell" rows="2" data-id="${item.id}" placeholder="ចុចកែប្រែភាសាខ្មែរ...">${escapeHtml(item.khmer_text || "")}</textarea>
                </td>
                <td>
                    <span class="speed-badge">${item.speed || "Auto"}</span>
                </td>
                <td>
                    <div class="duration-cell">
                        <button class="btn-row-play ${hasAudio ? 'has-audio' : ''}" data-id="${item.id}" title="${hasAudio ? 'ស្តាប់សំឡេងជួរនេះ' : 'បង្កើតសំឡេងជួរនេះ'}">
                            ${hasAudio ? '▶' : '🎙'}
                        </button>
                        <span>${item.duration_str || "- / 2.0s"}</span>
                    </div>
                </td>
                <td>
                    <span class="status-badge ${statusClass}">${item.status || "រង់ចាំ"}</span>
                </td>
            </tr>
        `;
    }).join("");

    dom.tableBody.innerHTML = rowsHtml;
    attachTableListeners();
    updateSummaryStats();
}

function getStatusClass(status) {
    if (!status || status === "រង់ចាំ") return "waiting";
    if (status.includes("កំពុង")) return "translating";
    if (status.includes("បកប្រែរួច") || status.includes("វិភាគរួច")) return "translated";
    if (status.includes("សំឡេងរួចរាល់") || status.includes("រួចរាល់")) return "ready";
    if (status.includes("បរាជ័យ")) return "failed";
    return "waiting";
}

function updateTableRow(item) {
    const rowEl = document.getElementById(`row-${item.id}`);
    if (!rowEl) return;

    // Update voice select
    const voiceSel = rowEl.querySelector(".row-voice-select");
    if (voiceSel) voiceSel.value = item.voice || "Auto";

    // Update echo
    const echoBox = rowEl.querySelector(".echo-checkbox");
    if (echoBox) echoBox.checked = item.echo === "Yes";

    // Update khmer textarea if not focused
    const txtArea = rowEl.querySelector(".khmer-input-cell");
    if (txtArea && document.activeElement !== txtArea) {
        txtArea.value = item.khmer_text || "";
    }

    // Update duration cell
    const durCell = rowEl.querySelector(".duration-cell");
    if (durCell) {
        const hasAudio = !!item.audio_url;
        const playBtn = durCell.querySelector(".btn-row-play");
        if (playBtn) {
            playBtn.className = `btn-row-play ${hasAudio ? 'has-audio' : ''}`;
            playBtn.innerHTML = hasAudio ? '▶' : '🎙';
        }
        const durText = durCell.querySelector("span");
        if (durText) durText.textContent = item.duration_str || "- / 2.0s";
    }

    // Update speed badge
    const speedBadge = rowEl.querySelector(".speed-badge");
    if (speedBadge) {
        speedBadge.textContent = item.speed || "Auto";
    }

    // Update status badge
    const badge = rowEl.querySelector(".status-badge");
    if (badge) {
        badge.className = `status-badge ${getStatusClass(item.status)}`;
        badge.textContent = item.status || "រង់ចាំ";
    }
}

function attachTableListeners() {
    // Double click to play row audio (matching main.py)
    document.querySelectorAll(".subtitle-table tbody tr").forEach(row => {
        row.addEventListener("doubleclick", () => {
            const id = parseInt(row.dataset.id);
            const item = state.items.find(it => it.id === id);
            if (item) playRowAudio(item);
        });
    });

    // Khmer input edit
    document.querySelectorAll(".khmer-input-cell").forEach(el => {
        el.addEventListener("input", (e) => {
            const id = parseInt(e.target.dataset.id);
            const item = state.items.find(it => it.id === id);
            if (item) {
                item.khmer_text = e.target.value;
                item.status = "បកប្រែរួច";
                updateSummaryStats();
            }
        });
    });

    // Voice dropdown change
    document.querySelectorAll(".row-voice-select").forEach(el => {
        el.addEventListener("change", (e) => {
            const id = parseInt(e.target.dataset.id);
            const item = state.items.find(it => it.id === id);
            if (item) item.voice = e.target.value;
        });
    });

    // Echo checkbox
    document.querySelectorAll(".echo-checkbox").forEach(el => {
        el.addEventListener("change", (e) => {
            const id = parseInt(e.target.dataset.id);
            const item = state.items.find(it => it.id === id);
            if (item) item.echo = e.target.checked ? "Yes" : "No";
        });
    });

    // Row Audio Play / Generate Button
    document.querySelectorAll(".btn-row-play").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const id = parseInt(btn.dataset.id);
            const item = state.items.find(it => it.id === id);
            if (!item) return;

            if (item.audio_url) {
                playRowAudio(item);
            } else {
                // Generate TTS on the fly for single row
                btn.innerHTML = '<span class="spinner-small"></span>';
                try {
                    const text = item.khmer_text || item.orig_text;
                    const res = await fetch("/api/tts-single-row", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            id: item.id,
                            text: text,
                            voice: item.voice || "Auto",
                            gender: item.gender || "ប្រុស",
                            echo: item.echo || "No",
                            speed: item.speed || "Default",
                            target_ms: item.target_ms || 2000,
                            rate: state.settings.rate,
                            pitch: state.settings.pitch
                        })
                    });
                    const data = await res.json();
                    if (data.success) {
                        item.audio_url = data.audio_url;
                        item.duration_ms = data.duration_ms;
                        item.duration_str = data.duration_str;
                        if (data.rate_used) item.speed = data.rate_used;
                        item.status = "សំឡេងរួចរាល់";
                        updateTableRow(item);
                        playRowAudio(item);
                        updateSummaryStats();
                    } else {
                        showToast(data.detail || "បរាជ័យក្នុងការបង្កើតសំឡេង", "error");
                        btn.innerHTML = '🎙';
                    }
                } catch (err) {
                    showToast("កំហុសក្នុងការបង្កើតសំឡេង", "error");
                    btn.innerHTML = '🎙';
                }
            }
        });
    });
}

function playRowAudio(item) {
    if (!item.audio_url) return;
    if (!dom.masterAudioElement.paused) {
        dom.masterAudioElement.pause();
        updateMasterPlayButtonState(false);
    }
    state.activeRowPlayingId = item.id;
    dom.rowAudioElement.src = item.audio_url;
    dom.rowAudioElement.play();

    // Visual highlight on row
    document.querySelectorAll(".subtitle-table tr.active-playback-row").forEach(r => r.classList.remove("active-playback-row"));
    const rowEl = document.getElementById(`row-${item.id}`);
    if (rowEl) rowEl.classList.add("active-playback-row");

    dom.rowAudioElement.onended = () => {
        state.activeRowPlayingId = null;
        if (rowEl) rowEl.classList.remove("active-playback-row");
    };
}

function updateSummaryStats() {
    const total = state.items.length;
    const transCount = state.items.filter(it => it.khmer_text && it.khmer_text.trim().length > 0).length;
    const audioCount = state.items.filter(it => it.audio_url).length;
    const remaining = total - audioCount;

    if (dom.statTotalCount) dom.statTotalCount.textContent = total;
    if (dom.statTransCount) dom.statTransCount.textContent = `${transCount}/${total}`;
    if (dom.statAudioCount) dom.statAudioCount.textContent = `${audioCount}/${total}`;
    if (dom.statRemainingCount) dom.statRemainingCount.textContent = remaining;

    if (dom.fileInfoLabel) {
        dom.fileInfoLabel.textContent = state.currentFilename ? `📄 ${state.currentFilename} (${total} ជួរ)` : "📄 មិនទាន់ផ្ទុកឯកសារ";
    }
    if (dom.progressStatusLabel && !state.isPipelineRunning) {
        dom.progressStatusLabel.textContent = total > 0 ? "ត្រៀមរួចរាល់" : "សូមជ្រើសរើសឯកសារ SRT";
    }
}

// Master Audio Controls & Karaoke Table Sync
function initMasterPlayer() {
    dom.btnMasterPlayPause.addEventListener("click", () => {
        if (!state.masterAudioUrl) {
            showToast("សូមចុច '💾 នាំចេញ' ឬបង្កើត Master Audio ជាមុនសិន!", "info");
            return;
        }

        if (dom.masterAudioElement.paused) {
            dom.masterAudioElement.play();
            updateMasterPlayButtonState(true);
        } else {
            dom.masterAudioElement.pause();
            updateMasterPlayButtonState(false);
        }
    });

    dom.masterAudioElement.addEventListener("timeupdate", () => {
        const cur = dom.masterAudioElement.currentTime;
        const dur = dom.masterAudioElement.duration || 0;
        dom.playerCurrentTime.textContent = formatTime(cur);
        dom.playerTotalDuration.textContent = formatTime(dur);

        if (dur > 0) {
            dom.masterTimelineSlider.value = (cur / dur) * 100;
        }

        // Auto-Sync table karaoke highlighting
        if (dom.autoScrollToggle.checked && state.items.length > 0) {
            const curMs = cur * 1000;
            const activeItem = state.items.find(it => curMs >= it.start_ms && curMs <= it.end_ms);
            
            document.querySelectorAll(".subtitle-table tr.active-playback-row").forEach(r => {
                if (!activeItem || r.id !== `row-${activeItem.id}`) {
                    r.classList.remove("active-playback-row");
                }
            });

            if (activeItem) {
                const rowEl = document.getElementById(`row-${activeItem.id}`);
                if (rowEl && !rowEl.classList.contains("active-playback-row")) {
                    rowEl.classList.add("active-playback-row");
                    rowEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
                }
            }
        }
    });

    dom.masterAudioElement.addEventListener("ended", () => {
        updateMasterPlayButtonState(false);
        document.querySelectorAll(".subtitle-table tr.active-playback-row").forEach(r => r.classList.remove("active-playback-row"));
    });

    dom.masterTimelineSlider.addEventListener("input", (e) => {
        const dur = dom.masterAudioElement.duration || 0;
        if (dur > 0) {
            dom.masterAudioElement.currentTime = (e.target.value / 100) * dur;
        }
    });

    dom.masterVolumeSlider.addEventListener("input", (e) => {
        dom.masterAudioElement.volume = parseFloat(e.target.value);
    });
}

function updateMasterPlayButtonState(isPlaying) {
    dom.playerIconPlay.style.display = isPlaying ? "none" : "inline";
    dom.playerIconPause.style.display = isPlaying ? "inline" : "none";
}

// Multi-File Helpers
function updateMultiFileDropdown() {
    if (!dom.multiFileDropdown) return;
    if (!state.fileLibrary || state.fileLibrary.length <= 1) {
        dom.filePathDisplay.style.display = "block";
        dom.multiFileDropdown.style.display = "none";
        return;
    }

    dom.filePathDisplay.style.display = "none";
    dom.multiFileDropdown.style.display = "block";
    dom.multiFileDropdown.innerHTML = "";

    let totalMergedLines = 0;
    state.fileLibrary.forEach((f, idx) => {
        totalMergedLines += f.items.length;
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `📁 [${idx + 1}/${state.fileLibrary.length}] ${f.filename} (${f.items.length} ជួរ)`;
        if (idx === state.currentFileIndex) opt.selected = true;
        dom.multiFileDropdown.appendChild(opt);
    });

    const mergeOpt = document.createElement("option");
    mergeOpt.value = "merge_all";
    mergeOpt.textContent = `🔗 បញ្ចូលឯកសារទាំង ${state.fileLibrary.length} ចូលគ្នាតែមួយ (សរុប ${totalMergedLines} ជួរ)`;
    dom.multiFileDropdown.appendChild(mergeOpt);
}

function mergeAllLoadedFiles() {
    if (!state.fileLibrary || state.fileLibrary.length === 0) return;
    const mergedItems = [];
    let currentId = 1;

    state.fileLibrary.forEach(fileObj => {
        fileObj.items.forEach(it => {
            mergedItems.push({
                ...it,
                id: currentId++
            });
        });
    });

    const mergedName = `merged_${state.fileLibrary.length}_episodes.srt`;
    state.items = mergedItems;
    state.currentFilename = mergedName;
    renderTable();
    showToast(`បានបញ្ចូល ${state.fileLibrary.length} ឯកសារចូលគ្នារួចរាល់! (សរុប ${mergedItems.length} ជួរ)`, "success");
}

// Action Handlers
function initToolbarHandlers() {
    // 1. File Upload
    // 1. File Upload (Supports Single & Multiple SRT files)
    dom.srtFileInput.addEventListener("change", async (e) => {
        const files = Array.from(e.target.files);
        if (!files || files.length === 0) return;

        if (files.length === 1) {
            const file = files[0];
            const formData = new FormData();
            formData.append("file", file);

            try {
                const res = await fetch("/api/parse-srt", { method: "POST", body: formData });
                const data = await res.json();
                if (data.success) {
                    state.fileLibrary = [{ filename: data.filename, items: data.items, masterAudioUrl: null }];
                    state.currentFileIndex = 0;
                    state.items = data.items;
                    state.currentFilename = data.filename;
                    dom.filePathDisplay.value = data.filename;
                    dom.filePathDisplay.style.display = "block";
                    if (dom.multiFileDropdown) dom.multiFileDropdown.style.display = "none";
                    renderTable();
                    showToast(`បានបើកឯកសារ ${data.filename} (${data.count} ជួរ)`, "success");
                } else {
                    showToast(data.detail || "បរាជ័យក្នុងការបើក SRT", "error");
                }
            } catch (err) {
                showToast("កំហុសក្នុងការ Upload ឯកសារ SRT", "error");
            }
        } else {
            // Multiple files selected
            showToast(`កំពុងអាន ${files.length} ឯកសារ SRT...`, "info");
            const loadedFiles = [];
            for (const file of files) {
                try {
                    const formData = new FormData();
                    formData.append("file", file);
                    const res = await fetch("/api/parse-srt", { method: "POST", body: formData });
                    const data = await res.json();
                    if (data.success) {
                        loadedFiles.push({
                            filename: data.filename,
                            items: data.items,
                            masterAudioUrl: null
                        });
                    }
                } catch (err) {
                    console.error("Error parsing", file.name, err);
                }
            }

            if (loadedFiles.length > 0) {
                state.fileLibrary = loadedFiles;
                state.currentFileIndex = 0;
                state.items = loadedFiles[0].items;
                state.currentFilename = loadedFiles[0].filename;

                updateMultiFileDropdown();
                renderTable();
                showToast(`បានបើកជោគជ័យ ${loadedFiles.length} ឯកសារ SRT! លោកអ្នកអាចចុច Dropdown ដើម្បីប្តូរឯកសារ ឬបញ្ចូលគ្នា។`, "success");
            } else {
                showToast("មិនអាចអានឯកសារ SRT បានឡើយ", "error");
            }
        }
    });

    // Multi-File Dropdown Switcher
    if (dom.multiFileDropdown) {
        dom.multiFileDropdown.addEventListener("change", (e) => {
            if (e.target.value === "merge_all") {
                mergeAllLoadedFiles();
            } else {
                const idx = parseInt(e.target.value);
                if (idx >= 0 && idx < state.fileLibrary.length) {
                    state.currentFileIndex = idx;
                    const cur = state.fileLibrary[idx];
                    state.items = cur.items;
                    state.currentFilename = cur.filename;
                    state.masterAudioUrl = cur.masterAudioUrl || null;
                    if (state.masterAudioUrl) {
                        dom.masterAudioElement.src = state.masterAudioUrl;
                        dom.btnDownloadMaster.href = state.masterAudioUrl;
                        dom.btnDownloadMaster.download = cur.filename.replace(/\.[^/.]+$/, "") + ".mp3";
                        dom.btnDownloadMaster.style.display = "inline-flex";
                        dom.masterTrackTitle.textContent = cur.filename.replace(/\.[^/.]+$/, "") + ".mp3";
                    } else {
                        dom.masterAudioElement.src = "";
                        dom.btnDownloadMaster.style.display = "none";
                        dom.masterTrackTitle.textContent = "Master Voiceover Audio";
                    }
                    renderTable();
                    showToast(`បានប្តូរទៅឯកសារ ${cur.filename} (${cur.items.length} ជួរ)`, "info");
                }
            }
        });
    }

    // Drag and Drop on Toolbar Card
    const dropZone = document.querySelector(".file-toolbar-card");
    if (dropZone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropZone.style.filter = "brightness(1.2)";
            }, false);
        });
        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropZone.style.filter = "";
            }, false);
        });
        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (!dt) return;
            const files = Array.from(dt.files).filter(f => f.name.toLowerCase().endsWith(".srt"));
            if (files.length > 0) {
                const dataTransfer = new DataTransfer();
                files.forEach(f => dataTransfer.items.add(f));
                dom.srtFileInput.files = dataTransfer.files;
                dom.srtFileInput.dispatchEvent(new Event('change'));
            }
        });
    }

    // 3. ⚡ Master Auto Start Button (One-click pipeline matching on_master_action_clicked)
    dom.btnMasterAction.addEventListener("click", async () => {
        if (state.isPipelineRunning) {
            // Cancel running pipeline
            await fetch("/api/cancel-operation", { method: "POST" });
            showToast("បានស្នើសុំបញ្ឈប់ដំណើរការ...", "info");
            return;
        }

        if (!state.items || state.items.length === 0) {
            showToast("សូមបើកឯកសារ SRT ជាមុនសិន!", "info");
            return;
        }
        if (state.settings.apiKeys.length === 0) {
            showToast("សូមបញ្ចូល Gemini API Key ក្នុង Settings ជាមុនសិន!", "error");
            dom.settingsModal.style.display = "flex";
            return;
        }

        try {
            const res = await fetch("/api/auto-start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    items: state.items,
                    api_keys: state.settings.apiKeys,
                    model_name: state.settings.modelName,
                    style: state.settings.style,
                    batch_size: state.settings.batchSize,
                    concurrency: state.settings.concurrency,
                    request_delay: state.settings.requestDelay,
                    rate: state.settings.rate,
                    pitch: state.settings.pitch,
                    bitrate: state.settings.bitrate,
                    filename: state.currentFilename
                })
            });
            const data = await res.json();
            showToast("បានចាប់ផ្តើមដំណើរការ Auto Start Pipeline...", "info");
        } catch (err) {
            showToast("កំហុសក្នុងការចាប់ផ្តើម Auto Pipeline", "error");
        }
    });

    // 4. Individual Buttons
    dom.btnAnalyzeGenders.addEventListener("click", () => {
        dom.btnMasterAction.click();
    });

    dom.btnStartTranslation.addEventListener("click", () => {
        dom.btnMasterAction.click();
    });

    dom.btnGenAllVoices.addEventListener("click", async () => {
        if (state.isPipelineRunning) {
            await fetch("/api/cancel-operation", { method: "POST" });
            showToast("បានស្នើសុំបញ្ឈប់ដំណើរការ...", "info");
            return;
        }

        if (!state.items || state.items.length === 0) {
            showToast("សូមបើកឯកសារ SRT ជាមុនសិន!", "info");
            return;
        }

        try {
            const res = await fetch("/api/gen-all-voices", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    items: state.items,
                    rate: state.settings.rate,
                    pitch: state.settings.pitch,
                    bitrate: state.settings.bitrate,
                    filename: state.currentFilename
                })
            });
            const data = await res.json();
            showToast("បានចាប់ផ្តើមបង្កើតសំឡេងទាំងអស់ (Turbo 16 Threads)...", "info");
        } catch (err) {
            showToast("កំហុសក្នុងការបង្កើតសំឡេង", "error");
        }
    });

    // 5. 💾 Export Master (2-in-1: Save SRT + Compile Master Audio)
    dom.btnExportMaster.addEventListener("click", async () => {
        if (!state.items || state.items.length === 0) {
            showToast("គ្មានទិន្នន័យ Subtitle ត្រូវនាំចេញឡើយ!", "info");
            return;
        }

        dom.btnExportMaster.innerHTML = '<span class="spinner-small"></span> <span class="btn-text">កំពុងនាំចេញ...</span>';
        try {
            const res = await fetch("/api/export-master", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    items: state.items,
                    include_gender_tag: true,
                    bitrate: state.settings.bitrate,
                    filename: state.currentFilename
                })
            });
            const data = await res.json();
            if (data.success) {
                const originalBaseName = (state.currentFilename || "master_voiceover").replace(/\.[^/.]+$/, "");
                const mp3FileName = originalBaseName + ".mp3";

                // Download SRT
                const srtBlob = new Blob([data.srt_content], { type: "text/plain;charset=utf-8" });
                const srtUrl = URL.createObjectURL(srtBlob);
                const aSrt = document.createElement("a");
                aSrt.href = srtUrl;
                aSrt.download = originalBaseName + "_translated.srt";
                document.body.appendChild(aSrt);
                aSrt.click();
                aSrt.remove();
                URL.revokeObjectURL(srtUrl);

                // Setup Master MP3
                if (data.master_url) {
                    state.masterAudioUrl = data.master_url;
                    dom.masterAudioElement.src = data.master_url;
                    dom.btnDownloadMaster.href = data.master_url;
                    dom.btnDownloadMaster.download = mp3FileName;
                    dom.btnDownloadMaster.style.display = "inline-flex";
                    dom.masterTrackTitle.textContent = mp3FileName;
                }

                showToast(`បាននាំចេញឯកសារ SRT និង ${mp3FileName} រួចរាល់ដោយជោគជ័យ!`, "success");
            }
        } catch (err) {
            showToast("កំហុសក្នុងការនាំចេញឯកសារ", "error");
        } finally {
            dom.btnExportMaster.innerHTML = '<span class="btn-icon">💾</span><span class="btn-text">នាំចេញ</span>';
        }
    });

    // Filter Search Box
    dom.tableFilterInput.addEventListener("input", () => {
        renderTable();
    });
}

// Settings Modal
function initSettingsModal() {
    dom.btnOpenSettings.addEventListener("click", () => {
        dom.settingsModal.style.display = "flex";
    });

    dom.btnCloseSettings.addEventListener("click", () => {
        dom.settingsModal.style.display = "none";
    });

    dom.btnCancelSettings.addEventListener("click", () => {
        dom.settingsModal.style.display = "none";
    });

    // Quick Model and Style Selects on Main UI
    if (dom.mainModelSelect) {
        dom.mainModelSelect.addEventListener("change", (e) => {
            state.settings.modelName = e.target.value;
            if (dom.settingsModel) dom.settingsModel.value = e.target.value;
            if (dom.activeModelLabel) dom.activeModelLabel.textContent = e.target.value;
            localStorage.setItem("pl_khmer_settings", JSON.stringify(state.settings));
            showToast(`🤖 បានប្តូរម៉ូដែល: ${e.target.value}`, "info");
        });
    }

    if (dom.mainStyleSelect) {
        dom.mainStyleSelect.addEventListener("change", (e) => {
            state.settings.style = e.target.value;
            if (dom.settingsStyle) dom.settingsStyle.value = e.target.value;
            localStorage.setItem("pl_khmer_settings", JSON.stringify(state.settings));
            showToast("🎭 បានប្តូររចនាប័ទ្មបកប្រែ", "info");
        });
    }

    // Toggle key visibility
    dom.btnToggleKeyVisibility.addEventListener("click", () => {
        if (dom.settingsApiKeys.style.webkitTextSecurity === "disc") {
            dom.settingsApiKeys.style.webkitTextSecurity = "none";
        } else {
            dom.settingsApiKeys.style.webkitTextSecurity = "disc";
        }
    });

    // Sliders label updates
    dom.settingsRateSlider.addEventListener("input", (e) => {
        const val = parseInt(e.target.value);
        dom.labelRateVal.textContent = `${val >= 0 ? "+" : ""}${val}%`;
    });

    dom.settingsPitchSlider.addEventListener("input", (e) => {
        const val = parseInt(e.target.value);
        dom.labelPitchVal.textContent = `${val >= 0 ? "+" : ""}${val}Hz`;
    });

    dom.settingsBatchSlider.addEventListener("input", (e) => {
        dom.labelBatchSize.textContent = e.target.value;
    });

    dom.settingsConcurrencySlider.addEventListener("input", (e) => {
        dom.labelConcurrency.textContent = e.target.value;
    });

    // Test Key
    dom.btnTestKey.addEventListener("click", async () => {
        const keys = dom.settingsApiKeys.value.trim().split(/[\r\n,;]+/);
        const testKey = keys.find(k => k.trim().length > 10);
        if (!testKey) {
            dom.keyTestResult.className = "key-test-msg error";
            dom.keyTestResult.textContent = "សូមបញ្ចូល API Key ជាមុនសិន!";
            return;
        }

        dom.testKeySpinner.style.display = "inline-block";
        dom.keyTestResult.className = "key-test-msg";
        dom.keyTestResult.textContent = "កំពុងតេស្តភ្ជាប់ Google Studio...";

        try {
            const res = await fetch("/api/test-key", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    api_key: testKey.trim(),
                    model_name: dom.settingsModel.value
                })
            });
            const data = await res.json();
            if (data.valid) {
                dom.keyTestResult.className = "key-test-msg success";
                dom.keyTestResult.textContent = data.message;
            } else {
                dom.keyTestResult.className = "key-test-msg error";
                dom.keyTestResult.textContent = data.message;
            }
        } catch (e) {
            dom.keyTestResult.className = "key-test-msg error";
            dom.keyTestResult.textContent = "បរាជ័យក្នុងការតភ្ជាប់";
        } finally {
            dom.testKeySpinner.style.display = "none";
        }
    });

    // Save Settings
    dom.btnSaveSettings.addEventListener("click", () => {
        const keys = dom.settingsApiKeys.value.trim().split(/[\r\n,;]+/).map(k => k.trim()).filter(k => k.length > 5);
        state.settings.apiKeys = keys;
        state.settings.modelName = dom.settingsModel.value;
        state.settings.style = dom.settingsStyle.value;
        state.settings.batchSize = parseInt(dom.settingsBatchSlider.value);
        state.settings.concurrency = parseInt(dom.settingsConcurrencySlider.value);

        const r = parseInt(dom.settingsRateSlider.value);
        state.settings.rate = `${r >= 0 ? "+" : ""}${r}%`;

        const p = parseInt(dom.settingsPitchSlider.value);
        state.settings.pitch = `${p >= 0 ? "+" : ""}${p}Hz`;

        if (dom.settingsBitrate) {
            state.settings.bitrate = dom.settingsBitrate.value;
        }

        localStorage.setItem("pl_khmer_settings", JSON.stringify(state.settings));
        dom.activeModelLabel.textContent = state.settings.modelName;
        if (dom.mainModelSelect) dom.mainModelSelect.value = state.settings.modelName;
        if (dom.mainStyleSelect) dom.mainStyleSelect.value = state.settings.style;
        dom.settingsModal.style.display = "none";
        showToast("ការកំណត់ត្រូវបានរក្សាទុកដោយជោគជ័យ!", "success");
    });
}

// Initial Settings Load
async function loadInitialSettings() {
    let backend = {};
    const saved = localStorage.getItem("pl_khmer_settings");
    if (saved) {
        try { state.settings = { ...state.settings, ...JSON.parse(saved) }; } catch (e) {}
    }

    try {
        const res = await fetch("/api/settings");
        backend = await res.json();
        if (backend.api_keys && (!state.settings.apiKeys || state.settings.apiKeys.length === 0)) {
            state.settings.apiKeys = backend.api_keys;
        }
        if (backend.gemini_model && !saved) state.settings.modelName = backend.gemini_model;
        if (backend.style && !saved) state.settings.style = backend.style;
        if (backend.batch_size && !saved) state.settings.batchSize = backend.batch_size;
        if (backend.concurrency && !saved) state.settings.concurrency = backend.concurrency;
        if (backend.bitrate && !saved) state.settings.bitrate = backend.bitrate;
    } catch (e) {
        console.warn("Could not fetch /api/settings:", e);
    }

    if (!Array.isArray(state.settings.apiKeys)) {
        state.settings.apiKeys = [];
    }

    // Fill modal inputs and main UI dropdowns
    dom.settingsApiKeys.value = state.settings.apiKeys.join("\n");
    dom.settingsModel.value = state.settings.modelName || "gemini-3.5-flash-lite";
    dom.settingsStyle.value = state.settings.style || "emotion_acting";
    if (dom.mainModelSelect) dom.mainModelSelect.value = state.settings.modelName || "gemini-3.5-flash-lite";
    if (dom.mainStyleSelect) dom.mainStyleSelect.value = state.settings.style || "emotion_acting";
    dom.activeModelLabel.textContent = state.settings.modelName;

    if (!saved || state.settings.rate === "+0%") {
        state.settings.rate = backend.rate || "+20%";
    }
    let rateNum = 20;
    if (state.settings.rate) {
        rateNum = parseInt(state.settings.rate.replace("%", "").replace("+", ""));
        if (isNaN(rateNum)) rateNum = 20;
    }
    dom.settingsRateSlider.value = rateNum;
    dom.labelRateVal.textContent = `${rateNum >= 0 ? "+" : ""}${rateNum}%`;

    const pitchStr = state.settings.pitch || "+0Hz";
    const pitchNum = parseInt(pitchStr.replace("Hz", "").replace("+", "")) || 0;
    dom.settingsPitchSlider.value = pitchNum;
    dom.labelPitchVal.textContent = `${pitchNum >= 0 ? "+" : ""}${pitchNum}Hz`;

    dom.settingsBatchSlider.value = state.settings.batchSize || 30;
    dom.labelBatchSize.textContent = state.settings.batchSize || 30;

    dom.settingsConcurrencySlider.value = state.settings.concurrency || 8;
    dom.labelConcurrency.textContent = state.settings.concurrency || 8;

    if (dom.settingsBitrate) {
        dom.settingsBitrate.value = state.settings.bitrate || "128k";
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// App Start
document.addEventListener("DOMContentLoaded", async () => {
    try { initWebSocket(); } catch (e) { console.error("WS error:", e); }
    try { await loadInitialSettings(); } catch (e) { console.error("Settings error:", e); }
    try { initMasterPlayer(); } catch (e) { console.error("Player error:", e); }
    try { initToolbarHandlers(); } catch (e) { console.error("Toolbar error:", e); }
    try { initSettingsModal(); } catch (e) { console.error("Modal error:", e); }
    try { renderTable(); } catch (e) { console.error("Table error:", e); }

    // Auto-load sample for instant user review
    setTimeout(() => {
        try {
            if (state.items.length === 0 && dom.btnLoadSample) dom.btnLoadSample.click();
        } catch (e) {}
    }, 400);
});
