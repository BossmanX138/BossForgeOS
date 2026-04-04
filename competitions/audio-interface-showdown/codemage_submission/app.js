const audio = document.getElementById('audio');
const trackTitle = document.getElementById('trackTitle');
const trackMeta = document.getElementById('trackMeta');
const trackCount = document.getElementById('trackCount');
const playlistEl = document.getElementById('playlist');
const recentList = document.getElementById('recentList');

const playPauseBtn = document.getElementById('playPauseBtn');
const stopBtn = document.getElementById('stopBtn');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const muteBtn = document.getElementById('muteBtn');
const shuffleBtn = document.getElementById('shuffleBtn');
const loopBtn = document.getElementById('loopBtn');

const seekBar = document.getElementById('seekBar');
const currentTimeEl = document.getElementById('currentTime');
const durationEl = document.getElementById('duration');
const volumeSlider = document.getElementById('volumeSlider');
const speedSelect = document.getElementById('speedSelect');

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const barsRoot = document.getElementById('bars');

const BAR_COUNT = 48;
const SEEK_MAX = 1000;
const SEEK_STEP_SECONDS = 5;

const state = {
  playlist: [],
  currentIndex: 0,
  recent: [],
  shuffle: false,
  loop: false,
  isSeeking: false
};

const generatedObjectUrls = [];
const bars = [];

let audioCtx;
let sourceNode;
let analyser;
let dataArray;
let visualizerFrame;

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) {
    return '00:00';
  }
  const total = Math.max(0, Math.floor(seconds));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function createBars() {
  for (let i = 0; i < BAR_COUNT; i += 1) {
    const bar = document.createElement('span');
    bar.className = 'bar';
    barsRoot.appendChild(bar);
    bars.push(bar);
  }
}

function createToneWavUrl({ frequency, durationSeconds, gain, name, artist }) {
  const sampleRate = 44100;
  const sampleCount = Math.floor(sampleRate * durationSeconds);
  const channels = 1;
  const bytesPerSample = 2;
  const blockAlign = channels * bytesPerSample;
  const byteRate = sampleRate * blockAlign;
  const dataSize = sampleCount * blockAlign;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  function writeString(offset, value) {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i));
    }
  }

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, dataSize, true);

  const attack = Math.floor(sampleRate * 0.05);
  const release = Math.floor(sampleRate * 0.12);

  for (let i = 0; i < sampleCount; i += 1) {
    const t = i / sampleRate;
    const carrier = Math.sin(2 * Math.PI * frequency * t);
    const harmonic = Math.sin(2 * Math.PI * frequency * 1.5 * t) * 0.35;
    const shimmer = Math.sin(2 * Math.PI * frequency * 2.35 * t) * 0.14;

    let envelope = 1;
    if (i < attack) {
      envelope = i / attack;
    } else if (i > sampleCount - release) {
      envelope = (sampleCount - i) / release;
    }

    const sample = clamp((carrier + harmonic + shimmer) * gain * envelope, -1, 1);
    view.setInt16(44 + i * 2, sample * 32767, true);
  }

  const blob = new Blob([buffer], { type: 'audio/wav' });
  const src = URL.createObjectURL(blob);
  generatedObjectUrls.push(src);

  return {
    title: name,
    artist,
    src,
    sourceType: 'generated'
  };
}

function loadDemoPlaylist() {
  state.playlist = [
    createToneWavUrl({
      frequency: 198,
      durationSeconds: 14,
      gain: 0.33,
      name: 'Forge Pulse',
      artist: 'CodeMage Ensemble'
    }),
    createToneWavUrl({
      frequency: 262,
      durationSeconds: 18,
      gain: 0.28,
      name: 'Signal Lantern',
      artist: 'Guild Array'
    }),
    createToneWavUrl({
      frequency: 330,
      durationSeconds: 15,
      gain: 0.3,
      name: 'Circuit Tide',
      artist: 'Aether Workshop'
    })
  ];

  state.currentIndex = 0;
  renderPlaylist();
  loadTrack(0, false);
}

function renderPlaylist() {
  playlistEl.innerHTML = '';

  state.playlist.forEach((track, index) => {
    const li = document.createElement('li');
    li.className = `playlist-item${index === state.currentIndex ? ' active' : ''}`;
    li.dataset.index = String(index);

    const title = document.createElement('strong');
    title.textContent = track.title;

    const meta = document.createElement('span');
    meta.className = 'meta';
    meta.textContent = `${track.artist} ${track.sourceType === 'local' ? '- local file' : '- demo synth'}`;

    li.appendChild(title);
    li.appendChild(meta);

    li.addEventListener('click', () => {
      loadTrack(index, true);
    });

    playlistEl.appendChild(li);
  });

  trackCount.textContent = `${state.playlist.length} ${state.playlist.length === 1 ? 'track' : 'tracks'}`;
}

function updateNowPlaying(track) {
  trackTitle.textContent = track ? track.title : 'No track loaded';
  trackMeta.textContent = track
    ? `${track.artist} ${track.sourceType === 'local' ? '- local file' : '- generated demo'}`
    : 'Drop audio files or use the built-in demo tracks.';
}

function loadTrack(index, shouldPlay) {
  if (index < 0 || index >= state.playlist.length) {
    return;
  }

  state.currentIndex = index;
  const track = state.playlist[index];
  audio.src = track.src;
  audio.load();

  updateNowPlaying(track);
  renderPlaylist();

  if (shouldPlay) {
    playCurrentTrack();
  } else {
    playPauseBtn.textContent = 'Play';
  }
}

function addRecent(track) {
  state.recent = [track, ...state.recent.filter((item) => item.src !== track.src)].slice(0, 5);
  recentList.innerHTML = '';

  state.recent.forEach((item) => {
    const li = document.createElement('li');
    li.textContent = `${item.title} - ${item.artist}`;
    recentList.appendChild(li);
  });
}

function nextIndex() {
  if (state.playlist.length <= 1) {
    return state.currentIndex;
  }

  if (state.shuffle) {
    let randomIndex = state.currentIndex;
    while (randomIndex === state.currentIndex) {
      randomIndex = Math.floor(Math.random() * state.playlist.length);
    }
    return randomIndex;
  }

  return (state.currentIndex + 1) % state.playlist.length;
}

function prevIndex() {
  if (state.playlist.length <= 1) {
    return state.currentIndex;
  }

  if (state.shuffle) {
    return nextIndex();
  }

  return (state.currentIndex - 1 + state.playlist.length) % state.playlist.length;
}

function ensureAudioContext() {
  if (!audioCtx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    audioCtx = new Ctx();
    sourceNode = audioCtx.createMediaElementSource(audio);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    dataArray = new Uint8Array(analyser.frequencyBinCount);

    sourceNode.connect(analyser);
    analyser.connect(audioCtx.destination);
  }

  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
}

async function playCurrentTrack() {
  if (!state.playlist.length) {
    return;
  }

  try {
    ensureAudioContext();
    await audio.play();
    playPauseBtn.textContent = 'Pause';
    addRecent(state.playlist[state.currentIndex]);
    startVisualizer();
  } catch (error) {
    console.error('Playback blocked:', error);
  }
}

function pausePlayback() {
  audio.pause();
  playPauseBtn.textContent = 'Play';
}

function stopPlayback() {
  audio.pause();
  audio.currentTime = 0;
  playPauseBtn.textContent = 'Play';
}

function updateTimeUi() {
  currentTimeEl.textContent = formatTime(audio.currentTime);
  durationEl.textContent = formatTime(audio.duration);

  if (!state.isSeeking && Number.isFinite(audio.duration) && audio.duration > 0) {
    const ratio = audio.currentTime / audio.duration;
    seekBar.value = String(Math.round(ratio * SEEK_MAX));
  }
}

function onTrackEnded() {
  if (state.loop) {
    audio.currentTime = 0;
    playCurrentTrack();
    return;
  }

  const next = nextIndex();
  loadTrack(next, true);
}

function setupKeyboardShortcuts() {
  window.addEventListener('keydown', (event) => {
    const activeTag = document.activeElement ? document.activeElement.tagName : '';
    const isInputLike = activeTag === 'INPUT' || activeTag === 'SELECT' || activeTag === 'TEXTAREA';

    if (event.code === 'Space' && !isInputLike) {
      event.preventDefault();
      if (audio.paused) {
        playCurrentTrack();
      } else {
        pausePlayback();
      }
      return;
    }

    if (event.key === 'ArrowLeft' && !isInputLike) {
      event.preventDefault();
      audio.currentTime = Math.max(0, audio.currentTime - SEEK_STEP_SECONDS);
      return;
    }

    if (event.key === 'ArrowRight' && !isInputLike) {
      event.preventDefault();
      if (Number.isFinite(audio.duration)) {
        audio.currentTime = Math.min(audio.duration, audio.currentTime + SEEK_STEP_SECONDS);
      }
      return;
    }

    if (event.key.toLowerCase() === 'm') {
      event.preventDefault();
      audio.muted = !audio.muted;
      muteBtn.textContent = audio.muted ? 'Unmute' : 'Mute';
    }
  });
}

function bindFileLoading() {
  const prevent = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((name) => {
    dropzone.addEventListener(name, prevent);
  });

  ['dragenter', 'dragover'].forEach((name) => {
    dropzone.addEventListener(name, () => dropzone.classList.add('active'));
  });

  ['dragleave', 'drop'].forEach((name) => {
    dropzone.addEventListener(name, () => dropzone.classList.remove('active'));
  });

  dropzone.addEventListener('drop', (event) => {
    const files = event.dataTransfer ? [...event.dataTransfer.files] : [];
    addLocalFiles(files);
  });

  fileInput.addEventListener('change', (event) => {
    const files = event.target.files ? [...event.target.files] : [];
    addLocalFiles(files);
    fileInput.value = '';
  });
}

function addLocalFiles(files) {
  const audioFiles = files.filter((file) => file.type.startsWith('audio/'));
  if (!audioFiles.length) {
    return;
  }

  const entries = audioFiles.map((file) => ({
    title: file.name.replace(/\.[^/.]+$/, ''),
    artist: 'Local Source',
    src: URL.createObjectURL(file),
    sourceType: 'local'
  }));

  state.playlist = [...state.playlist, ...entries];
  renderPlaylist();

  if (!audio.src) {
    loadTrack(0, false);
  }
}

function startVisualizer() {
  if (!analyser || !dataArray) {
    return;
  }

  const draw = () => {
    analyser.getByteFrequencyData(dataArray);

    for (let i = 0; i < bars.length; i += 1) {
      const sourceIndex = Math.floor((i / bars.length) * dataArray.length);
      const magnitude = dataArray[sourceIndex] / 255;
      const height = 8 + magnitude * 108;
      bars[i].style.height = `${height}px`;
      bars[i].style.opacity = String(0.35 + magnitude * 0.7);
      bars[i].style.animation = 'none';
    }

    visualizerFrame = requestAnimationFrame(draw);
  };

  cancelAnimationFrame(visualizerFrame);
  draw();
}

function initializeEvents() {
  playPauseBtn.addEventListener('click', () => {
    if (audio.paused) {
      playCurrentTrack();
    } else {
      pausePlayback();
    }
  });

  stopBtn.addEventListener('click', stopPlayback);

  nextBtn.addEventListener('click', () => {
    loadTrack(nextIndex(), true);
  });

  prevBtn.addEventListener('click', () => {
    loadTrack(prevIndex(), true);
  });

  muteBtn.addEventListener('click', () => {
    audio.muted = !audio.muted;
    muteBtn.textContent = audio.muted ? 'Unmute' : 'Mute';
  });

  shuffleBtn.addEventListener('click', () => {
    state.shuffle = !state.shuffle;
    shuffleBtn.setAttribute('aria-pressed', String(state.shuffle));
    shuffleBtn.textContent = state.shuffle ? 'Shuffle On' : 'Shuffle Off';
  });

  loopBtn.addEventListener('click', () => {
    state.loop = !state.loop;
    loopBtn.setAttribute('aria-pressed', String(state.loop));
    loopBtn.textContent = state.loop ? 'Loop On' : 'Loop Off';
  });

  volumeSlider.addEventListener('input', (event) => {
    const nextVolume = Number(event.target.value);
    audio.volume = clamp(nextVolume, 0, 1);
  });

  speedSelect.addEventListener('change', (event) => {
    const rate = Number(event.target.value);
    audio.playbackRate = clamp(rate, 0.5, 2);
  });

  seekBar.addEventListener('pointerdown', () => {
    state.isSeeking = true;
  });

  seekBar.addEventListener('pointerup', () => {
    state.isSeeking = false;
  });

  seekBar.addEventListener('input', () => {
    if (!Number.isFinite(audio.duration) || audio.duration <= 0) {
      return;
    }

    const ratio = Number(seekBar.value) / SEEK_MAX;
    audio.currentTime = clamp(ratio * audio.duration, 0, audio.duration);
  });

  audio.addEventListener('loadedmetadata', updateTimeUi);
  audio.addEventListener('timeupdate', updateTimeUi);
  audio.addEventListener('ended', onTrackEnded);
  audio.addEventListener('pause', () => {
    if (playPauseBtn.textContent !== 'Play') {
      playPauseBtn.textContent = 'Play';
    }
  });
}

function initialize() {
  createBars();
  initializeEvents();
  setupKeyboardShortcuts();
  bindFileLoading();

  audio.volume = Number(volumeSlider.value);
  audio.playbackRate = Number(speedSelect.value);

  loadDemoPlaylist();
  updateTimeUi();
}

window.addEventListener('beforeunload', () => {
  generatedObjectUrls.forEach((url) => URL.revokeObjectURL(url));
});

initialize();
