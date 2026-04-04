const elements = {
  playPauseBtn: document.getElementById("playPauseBtn"),
  stopBtn: document.getElementById("stopBtn"),
  prevBtn: document.getElementById("prevBtn"),
  nextBtn: document.getElementById("nextBtn"),
  muteBtn: document.getElementById("muteBtn"),
  seekBar: document.getElementById("seekBar"),
  volumeSlider: document.getElementById("volumeSlider"),
  currentTime: document.getElementById("currentTime"),
  duration: document.getElementById("duration"),
  trackTitle: document.getElementById("trackTitle"),
  trackMeta: document.getElementById("trackMeta"),
  playlist: document.getElementById("playlist"),
  loopToggle: document.getElementById("loopToggle"),
  shuffleToggle: document.getElementById("shuffleToggle"),
  speedSelect: document.getElementById("speedSelect"),
  visualizer: document.getElementById("visualizer"),
  dropZone: document.getElementById("dropZone"),
  fileInput: document.getElementById("fileInput"),
};

const audio = new Audio();
audio.preload = "metadata";
audio.volume = Number(elements.volumeSlider.value);

const state = {
  tracks: [],
  currentIndex: -1,
  isSeeking: false,
};

let audioCtx;
let analyser;
let sourceNode;
let animationId;

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function generateToneWav({ freq = 220, seconds = 6, volume = 0.35, fade = 0.02 }) {
  const sampleRate = 44100;
  const totalSamples = Math.floor(sampleRate * seconds);
  const bytesPerSample = 2;
  const blockAlign = bytesPerSample;
  const dataSize = totalSamples * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  let offset = 0;
  const writeString = (str) => {
    for (let i = 0; i < str.length; i += 1) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
    offset += str.length;
  };

  writeString("RIFF");
  view.setUint32(offset, 36 + dataSize, true); offset += 4;
  writeString("WAVE");
  writeString("fmt ");
  view.setUint32(offset, 16, true); offset += 4;
  view.setUint16(offset, 1, true); offset += 2;
  view.setUint16(offset, 1, true); offset += 2;
  view.setUint32(offset, sampleRate, true); offset += 4;
  view.setUint32(offset, sampleRate * blockAlign, true); offset += 4;
  view.setUint16(offset, blockAlign, true); offset += 2;
  view.setUint16(offset, bytesPerSample * 8, true); offset += 2;
  writeString("data");
  view.setUint32(offset, dataSize, true); offset += 4;

  for (let i = 0; i < totalSamples; i += 1) {
    const t = i / sampleRate;
    const fadeIn = Math.min(1, t / fade);
    const fadeOut = Math.min(1, (seconds - t) / fade);
    const envelope = Math.min(fadeIn, fadeOut);
    const sample =
      Math.sin(2 * Math.PI * freq * t) * 0.65 +
      Math.sin(2 * Math.PI * (freq * 2) * t) * 0.2 +
      Math.sin(2 * Math.PI * (freq * 0.5) * t) * 0.15;

    const value = Math.max(-1, Math.min(1, sample * volume * envelope));
    view.setInt16(44 + i * 2, value * 32767, true);
  }

  const blob = new Blob([buffer], { type: "audio/wav" });
  return URL.createObjectURL(blob);
}

function createStarterPlaylist() {
  const tracks = [
    { title: "Neon Pulse", durationHint: "0:12", url: generateToneWav({ freq: 190, seconds: 12 }) },
    { title: "Copper Drift", durationHint: "0:10", url: generateToneWav({ freq: 260, seconds: 10 }) },
    { title: "Solar Bassline", durationHint: "0:14", url: generateToneWav({ freq: 128, seconds: 14 }) },
  ];

  tracks.forEach((track) => state.tracks.push({
    ...track,
    source: "Built-in",
  }));
}

function renderPlaylist() {
  elements.playlist.innerHTML = "";

  state.tracks.forEach((track, index) => {
    const item = document.createElement("li");
    item.className = "track-item";
    item.tabIndex = 0;
    if (index === state.currentIndex) item.classList.add("active");

    item.innerHTML = `
      <span class="name">${track.title}</span>
      <span class="info">${track.source || "Local"} ${track.durationHint ? "- " + track.durationHint : ""}</span>
    `;

    item.addEventListener("click", () => loadTrack(index, true));
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        loadTrack(index, true);
      }
    });

    elements.playlist.appendChild(item);
  });
}

function updateNowPlaying() {
  const track = state.tracks[state.currentIndex];
  if (!track) {
    elements.trackTitle.textContent = "No track selected";
    elements.trackMeta.textContent = "Choose from the queue or drop your own files";
    return;
  }

  elements.trackTitle.textContent = track.title;
  const rate = Number(elements.speedSelect.value).toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  elements.trackMeta.textContent = `${track.source || "Local"} | ${audio.muted ? "Muted" : "Volume " + Math.round(audio.volume * 100) + "%"} | ${rate}x`;
}

function updatePlayButton() {
  elements.playPauseBtn.textContent = audio.paused ? "Play" : "Pause";
}

function loadTrack(index, autoplay = false) {
  const track = state.tracks[index];
  if (!track) return;

  state.currentIndex = index;
  audio.src = track.url;
  audio.load();
  updateNowPlaying();
  renderPlaylist();

  if (autoplay) {
    audio.play().catch(() => {
      updatePlayButton();
    });
  }

  updatePlayButton();
}

function getNextIndex(direction = 1) {
  const count = state.tracks.length;
  if (count === 0) return -1;

  if (elements.shuffleToggle.checked) {
    if (count === 1) return state.currentIndex;
    let idx = state.currentIndex;
    while (idx === state.currentIndex) {
      idx = Math.floor(Math.random() * count);
    }
    return idx;
  }

  if (state.currentIndex < 0) return 0;
  return (state.currentIndex + direction + count) % count;
}

function playNext(direction = 1, autoplay = true) {
  const nextIndex = getNextIndex(direction);
  if (nextIndex < 0) return;
  loadTrack(nextIndex, autoplay);
}

function stopPlayback() {
  audio.pause();
  audio.currentTime = 0;
  elements.seekBar.value = "0";
  elements.currentTime.textContent = "0:00";
  updatePlayButton();
}

function togglePlayPause() {
  if (!audio.src && state.tracks.length > 0) {
    loadTrack(0, false);
  }

  if (audio.paused) {
    audio.play().catch(() => {
      updatePlayButton();
    });
  } else {
    audio.pause();
  }
}

function ensureAudioGraph() {
  if (audioCtx) return;
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  sourceNode = audioCtx.createMediaElementSource(audio);
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  sourceNode.connect(analyser);
  analyser.connect(audioCtx.destination);
  drawVisualizer();
}

function drawVisualizer() {
  const canvas = elements.visualizer;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width * dpr));
  const height = Math.max(1, Math.floor(rect.height * dpr));

  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }

  const bufferLength = analyser ? analyser.frequencyBinCount : 64;
  const data = new Uint8Array(bufferLength);

  const render = () => {
    if (analyser) {
      analyser.getByteFrequencyData(data);
    } else {
      data.fill(0);
    }

    ctx.clearRect(0, 0, width, height);

    const bars = 52;
    const gap = width * 0.004;
    const barWidth = (width - gap * (bars - 1)) / bars;

    for (let i = 0; i < bars; i += 1) {
      const idx = Math.floor((i / bars) * data.length);
      const value = data[idx] / 255;
      const barHeight = Math.max(6, value * (height * 0.9));
      const x = i * (barWidth + gap);
      const y = height - barHeight;

      const gradient = ctx.createLinearGradient(0, y, 0, height);
      gradient.addColorStop(0, "rgba(244,185,58,0.95)");
      gradient.addColorStop(0.55, "rgba(70,210,193,0.88)");
      gradient.addColorStop(1, "rgba(130,176,226,0.25)");

      ctx.fillStyle = gradient;
      ctx.fillRect(x, y, barWidth, barHeight);
    }

    animationId = requestAnimationFrame(render);
  };

  cancelAnimationFrame(animationId);
  render();
}

function setMute(nextMuted) {
  audio.muted = nextMuted;
  elements.muteBtn.setAttribute("aria-pressed", String(audio.muted));
  elements.muteBtn.textContent = audio.muted ? "Unmute" : "Mute";
  updateNowPlaying();
}

function seekBy(seconds) {
  if (!Number.isFinite(audio.duration)) return;
  audio.currentTime = Math.min(audio.duration, Math.max(0, audio.currentTime + seconds));
}

function loadUserFiles(fileList) {
  const accepted = Array.from(fileList).filter((file) => file.type.startsWith("audio/"));
  if (accepted.length === 0) return;

  accepted.forEach((file) => {
    state.tracks.push({
      title: file.name.replace(/\.[^.]+$/, ""),
      durationHint: "",
      url: URL.createObjectURL(file),
      source: "User file",
    });
  });

  renderPlaylist();
  if (state.currentIndex < 0) {
    loadTrack(0, false);
  }
}

function handleKeyboard(event) {
  const activeTag = document.activeElement?.tagName;
  const typing = activeTag === "INPUT" || activeTag === "TEXTAREA" || activeTag === "SELECT";

  if (event.key === " " && !typing) {
    event.preventDefault();
    ensureAudioGraph();
    togglePlayPause();
    return;
  }

  if (event.key === "ArrowLeft" && !typing) {
    event.preventDefault();
    seekBy(-5);
    return;
  }

  if (event.key === "ArrowRight" && !typing) {
    event.preventDefault();
    seekBy(5);
    return;
  }

  if (event.key.toLowerCase() === "m") {
    event.preventDefault();
    setMute(!audio.muted);
  }
}

function bindEvents() {
  document.addEventListener("keydown", handleKeyboard);

  const wakeAudio = () => ensureAudioGraph();
  ["pointerdown", "keydown", "touchstart"].forEach((evt) => {
    window.addEventListener(evt, wakeAudio, { once: true, passive: true });
  });

  elements.playPauseBtn.addEventListener("click", () => {
    ensureAudioGraph();
    togglePlayPause();
  });

  elements.stopBtn.addEventListener("click", stopPlayback);
  elements.prevBtn.addEventListener("click", () => playNext(-1, true));
  elements.nextBtn.addEventListener("click", () => playNext(1, true));

  elements.seekBar.addEventListener("input", () => {
    if (!Number.isFinite(audio.duration)) return;
    state.isSeeking = true;
    const pct = Number(elements.seekBar.value) / Number(elements.seekBar.max);
    audio.currentTime = pct * audio.duration;
    elements.currentTime.textContent = formatTime(audio.currentTime);
  });

  elements.seekBar.addEventListener("change", () => {
    state.isSeeking = false;
  });

  elements.volumeSlider.addEventListener("input", () => {
    audio.volume = Number(elements.volumeSlider.value);
    if (audio.volume > 0 && audio.muted) setMute(false);
    updateNowPlaying();
  });

  elements.muteBtn.addEventListener("click", () => setMute(!audio.muted));

  elements.speedSelect.addEventListener("change", () => {
    audio.playbackRate = Number(elements.speedSelect.value);
    updateNowPlaying();
  });

  audio.addEventListener("timeupdate", () => {
    if (!state.isSeeking && Number.isFinite(audio.duration) && audio.duration > 0) {
      const pct = (audio.currentTime / audio.duration) * Number(elements.seekBar.max);
      elements.seekBar.value = String(Math.floor(pct));
    }
    elements.currentTime.textContent = formatTime(audio.currentTime);
  });

  audio.addEventListener("loadedmetadata", () => {
    elements.duration.textContent = formatTime(audio.duration);
    elements.currentTime.textContent = formatTime(audio.currentTime);
    const track = state.tracks[state.currentIndex];
    if (track) {
      track.durationHint = formatTime(audio.duration);
      renderPlaylist();
      updateNowPlaying();
    }
  });

  audio.addEventListener("play", updatePlayButton);
  audio.addEventListener("pause", updatePlayButton);

  audio.addEventListener("ended", () => {
    if (elements.loopToggle.checked) {
      audio.currentTime = 0;
      audio.play().catch(() => {});
      return;
    }
    playNext(1, true);
  });

  const stopDragDefault = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };

  ["dragenter", "dragover", "dragleave", "drop"].forEach((name) => {
    elements.dropZone.addEventListener(name, stopDragDefault);
  });

  ["dragenter", "dragover"].forEach((name) => {
    elements.dropZone.addEventListener(name, () => elements.dropZone.classList.add("drag"));
  });

  ["dragleave", "drop"].forEach((name) => {
    elements.dropZone.addEventListener(name, () => elements.dropZone.classList.remove("drag"));
  });

  elements.dropZone.addEventListener("drop", (event) => {
    const files = event.dataTransfer?.files;
    if (files) loadUserFiles(files);
  });

  elements.fileInput.addEventListener("change", () => {
    if (elements.fileInput.files) loadUserFiles(elements.fileInput.files);
    elements.fileInput.value = "";
  });

  window.addEventListener("resize", () => {
    if (analyser) drawVisualizer();
  });
}

function init() {
  createStarterPlaylist();
  bindEvents();
  renderPlaylist();
  loadTrack(0, false);
  drawVisualizer();
}

init();
