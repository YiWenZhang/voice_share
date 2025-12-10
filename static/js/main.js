document.addEventListener("DOMContentLoaded", () => {
  initSliderVerification();
  initGlobalHostControls();
  initChatControls();
  initRoomSync();
  initMusicAutofill();
});

// --- 1. 聊天发送逻辑 ---
function initChatControls() {
  const chatForm = document.querySelector('.chat-form');
  if (!chatForm) return;

  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = chatForm.querySelector('input[name="content"]');
    const btn = chatForm.querySelector('.send-btn');
    const content = input.value.trim();
    if (!content) return;

    btn.disabled = true;
    btn.style.opacity = '0.5';
    const formData = new FormData(chatForm);

    try {
      const response = await fetch(chatForm.action, {
        method: 'POST',
        body: formData
      });
      if (response.ok) {
        input.value = '';
        if (window.manualRefreshState) await window.manualRefreshState();
        const chatLog = document.querySelector("#chat-log");
        if(chatLog) chatLog.scrollTop = chatLog.scrollHeight;
      }
    } catch (err) {
      console.error("网络错误", err);
    } finally {
      btn.disabled = false;
      btn.style.opacity = '1';
      input.focus();
    }
  });
}

// --- 2. 房主控制逻辑 ---
function initGlobalHostControls() {
  document.body.addEventListener('click', async (e) => {
    const btn = e.target.closest('.control-btn');
    if (!btn) return;
    e.preventDefault();

    if (!window.roomConfig || !window.roomConfig.toggleUrl) return;

    const originalOpacity = btn.style.opacity;
    btn.style.opacity = '0.6';
    btn.style.cursor = 'wait';

    const formData = new FormData();
    const action = btn.value || btn.getAttribute('value');
    formData.append('action', action);

    const form = btn.closest('form');
    // 获取 CSRF Token (优先从当前表单取，取不到从页面其他地方取)
    let csrfVal = '';
    if (form) {
        const csrf = form.querySelector('input[name="csrf_token"]');
        if (csrf) csrfVal = csrf.value;
    }
    if (!csrfVal) {
        const anyCsrf = document.querySelector('input[name="csrf_token"]');
        if (anyCsrf) csrfVal = anyCsrf.value;
    }
    formData.append('csrf_token', csrfVal);

    const audio = document.querySelector('#room-audio');
    let pos = 0;
    if (audio && !isNaN(audio.currentTime)) {
      pos = audio.currentTime;
    }
    formData.append('position', pos);

    try {
      const response = await fetch(window.roomConfig.toggleUrl, {
        method: 'POST',
        body: formData
      });
      if (response.ok) {
        if (window.manualRefreshState) await window.manualRefreshState();
      } else {
          console.error("请求失败", response.status);
      }
    } catch (err) {
      console.error("网络错误:", err);
    } finally {
      if (btn) {
        btn.style.opacity = originalOpacity || '1';
        btn.style.cursor = 'pointer';
      }
    }
  });
}

// --- 3. 房间同步逻辑 (核心) ---
function initRoomSync() {
  if (!window.roomConfig) return;
  const { stateUrl, audioSelector, isOwner, toggleUrl } = window.roomConfig;
  const audio = document.querySelector(audioSelector);

  const label = document.querySelector("#state-label");
  const trackLabel = document.querySelector("#current-track-label");
  const statusIndicator = document.querySelector(".status-indicator");
  const statusDot = document.querySelector(".status-dot");
  const hostBtnWrapper = document.querySelector("#host-btn-wrapper");
  const chatLog = document.querySelector("#chat-log");
  const playlistContainer = document.querySelector(".playlist-scroll-area");

  const progressFill = document.querySelector("#progress-fill");
  const timeCurrent = document.querySelector("#time-current");
  const timeDuration = document.querySelector("#time-duration");
  const vinylWrapper = document.querySelector('.vinyl-wrapper');

  // 本地进度驱动
  if (audio) {
    audio.addEventListener("timeupdate", () => {
      const current = audio.currentTime || 0;
      const duration = audio.duration || 0;
      if (timeCurrent) timeCurrent.textContent = formatTime(current);
      if (timeDuration && duration > 0 && duration !== Infinity) {
          timeDuration.textContent = formatTime(duration);
      }
      if (progressFill && duration > 0 && duration !== Infinity) {
        const percent = (current / duration) * 100;
        progressFill.style.width = `${percent}%`;
      }
    });
    audio.addEventListener("loadedmetadata", () => {
      if (timeDuration && audio.duration && audio.duration !== Infinity) {
        timeDuration.textContent = formatTime(audio.duration);
      }
    });
  }

  // 同步状态
  async function refreshState() {
    try {
      const response = await fetch(stateUrl);
      if (!response.ok) return;
      const state = await response.json();

      // UI 更新
      if (label) label.textContent = state.playback_status === "playing" ? "播放中" : "已暂停";
      if (statusDot) {
        statusDot.classList.remove('playing', 'paused');
        statusDot.classList.add(state.playback_status);
      }
      if (trackLabel) {
        const newTitle = state.current_track_name || "等待播放...";
        if (trackLabel.textContent.trim() !== newTitle) trackLabel.textContent = newTitle;
      }
      if (statusIndicator) {
        statusIndicator.textContent = state.is_active ? "正在营业" : "已打烊";
        statusIndicator.className = `status-indicator ${state.is_active ? 'active' : 'closed'}`;
      }

      // 按钮切换
      if (hostBtnWrapper) {
          const currentBtn = hostBtnWrapper.querySelector('.control-btn');
          if (currentBtn) {
              const btnAction = currentBtn.value || currentBtn.getAttribute('value');
              if (state.playback_status === 'playing' && btnAction === 'play') {
                  hostBtnWrapper.innerHTML = `
                    <button class="control-btn pause" name="action" value="pause" title="全员暂停">
                      <i class="ri-pause-mini-fill"></i> 暂停全员
                    </button>`;
              } else if (state.playback_status !== 'playing' && btnAction === 'pause') {
                  hostBtnWrapper.innerHTML = `
                    <button class="control-btn play" name="action" value="play" title="全员播放">
                      <i class="ri-play-mini-fill"></i> 播放全员
                    </button>`;
              }
          }
      }

      // 歌单同步 (修复：动态更新歌单)
      if (playlistContainer && state.playlist) {
          updatePlaylistUI(playlistContainer, state.playlist, state.current_track_name, isOwner, toggleUrl);
      }

      // 音频逻辑
      if (audio && state.is_active) {
          if (state.current_track_file) {
            const targetSrc = `/static/uploads/music/${state.current_track_file}`;
            const currentSrcPath = decodeURIComponent(audio.src).split('/static/uploads/music/')[1];

            // 切歌
            if (currentSrcPath !== state.current_track_file) {
              audio.src = targetSrc;
              if (state.current_position > 0) audio.currentTime = state.current_position;
              try {
                  await audio.load();
                  if (state.playback_status === "playing") audio.play().catch(() => {});
              } catch (e) { console.error(e); }
            }

            // 进度修正
            if (state.current_position !== undefined && state.current_position !== null) {
                 const diff = Math.abs(audio.currentTime - state.current_position);
                 if (state.playback_status === "paused") {
                     if (diff > 0.5) audio.currentTime = state.current_position;
                 }
                 else if (state.playback_status === "playing") {
                     if (isOwner && !audio.paused) {
                         if (diff > 5) audio.currentTime = state.current_position;
                     } else {
                         if (diff > 2) audio.currentTime = state.current_position;
                     }
                 }
            }

            // 播放控制
            if (state.playback_status === "playing") {
                if (audio.paused) audio.play().catch(() => {});
                if (vinylWrapper) vinylWrapper.classList.add('spinning');
            } else {
                if (!audio.paused) audio.pause();
                if (vinylWrapper) vinylWrapper.classList.remove('spinning');
            }
          }
      }

      // 聊天同步
      if (chatLog && state.messages) updateChatLog(chatLog, state.messages);

    } catch (error) {
      console.error("Sync error:", error);
    }
  }

  window.manualRefreshState = refreshState;
  refreshState();
  setInterval(refreshState, 2000);
}

// --- 4. 歌单渲染 (新增) ---
function updatePlaylistUI(container, playlist, currentTrackName, isOwner, toggleUrl) {
    // 简单比对：如果长度或第一首歌ID不同，或者切歌了，则重绘
    // 为了性能，可以做细致比对，但这里简单起见，直接重绘内容字符串然后比对
    let html = '';

    // 获取页面上的 CSRF token 供动态表单使用
    const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';

    if (playlist.length === 0) {
        html = '<div class="empty-list-placeholder">队列空空如也</div>';
    } else {
        playlist.forEach(item => {
            const isPlaying = (item.title === currentTrackName);
            let actionBtn = '';

            // 只有房主显示切歌按钮
            if (isOwner) {
                // 注意：动态生成的表单不走 body click 代理，因为它们是新元素
                // 但我们的 document.body.addEventListener 代理了所有 .control-btn
                // 这里切歌按钮是 submit，我们只要确保它是 control-btn 或者我们手动 fetch
                // 简单点：用普通的 form submit，由 body 代理拦截，或者我们给它加上 class="control-btn"
                // 这里我们构造一个标准的 form
                actionBtn = `
                    <form method="post" action="${toggleUrl}" class="playlist-action-form">
                        <input type="hidden" name="csrf_token" value="${csrfToken}" />
                        <input type="hidden" name="music_id" value="${item.music_id}" />
                        <button type="submit" class="icon-btn-sm control-btn" title="切歌">
                            <i class="ri-play-mini-fill"></i>
                        </button>
                    </form>
                `;
            }

            html += `
                <div class="playlist-item ${isPlaying ? 'playing' : ''}">
                    <div class="item-info">
                        <span class="item-title">${escapeHtml(item.title)}</span>
                        ${isPlaying ? '<span class="playing-badge"><i class="ri-volume-up-line"></i></span>' : ''}
                    </div>
                    ${actionBtn}
                </div>
            `;
        });
    }

    // 只有当 HTML 发生变化时才写入 DOM，防止闪烁和滚动条重置
    if (container.innerHTML.trim() !== html.trim()) {
        container.innerHTML = html;
    }
}

// --- 5. 聊天记录更新 ---
function updateChatLog(container, messages) {
    const existingItems = container.querySelectorAll('.chat-bubble-row');
    const existingIds = new Set();
    existingItems.forEach(el => {
        if (el.dataset.id) existingIds.add(parseInt(el.dataset.id));
    });
    let hasNew = false;
    const noMsg = container.querySelector('.no-msg');

    messages.forEach(msg => {
        if (!existingIds.has(msg.id)) {
            if (noMsg) noMsg.remove();
            const html = `
                <div class="chat-bubble-row" data-id="${msg.id}">
                    <img src="${msg.author_avatar}" class="chat-avatar-sm" />
                    <div class="chat-content-wrap">
                        <div class="chat-meta">
                            <span class="chat-name">${escapeHtml(msg.author_name)}</span>
                            <span class="chat-time">${msg.created_at}</span>
                        </div>
                        <div class="chat-bubble">${escapeHtml(msg.content)}</div>
                    </div>
                </div>`;
            container.insertAdjacentHTML('beforeend', html);
            hasNew = true;
        }
    });
    if (hasNew) container.scrollTop = container.scrollHeight;
}

// --- 6. 辅助函数 ---
function initSliderVerification() {
  document.querySelectorAll(".slider-verify").forEach((wrapper) => {
    const thumb = wrapper.querySelector(".slider-thumb");
    const track = wrapper.querySelector(".slider-track");
    const tip = wrapper.querySelector(".slider-tip");
    const hiddenInputId = wrapper.dataset.target;
    const hiddenInput = document.getElementById(hiddenInputId);
    if (!thumb || !track || !hiddenInput) return;
    let isDragging = false;
    let startX = 0; let currentX = 0;
    const maxOffset = track.offsetWidth - thumb.offsetWidth - 8;
    function setVerified() { hiddenInput.value = "verified"; tip.textContent = "验证完成"; track.classList.add("verified"); }
    function resetSlider() { hiddenInput.value = ""; thumb.style.transform = "translateX(0px)"; tip.textContent = "拖动滑块完成验证"; track.classList.remove("verified"); }
    thumb.addEventListener("pointerdown", (e) => { isDragging = true; startX = e.clientX || e.touches?.[0]?.clientX; thumb.setPointerCapture(e.pointerId || 1); });
    window.addEventListener("pointermove", (e) => { if (!isDragging) return; const clientX = e.clientX || e.touches?.[0]?.clientX; const diff = clientX - startX; currentX = Math.min(Math.max(0, diff), maxOffset); thumb.style.transform = `translateX(${currentX}px)`; if (currentX >= maxOffset) { isDragging = false; setVerified(); } });
    window.addEventListener("pointerup", (e) => { if (!isDragging) return; isDragging = false; if (currentX < maxOffset) resetSlider(); else setVerified(); thumb.releasePointerCapture(e.pointerId || 1); });
    resetSlider();
  });
}

function initMusicAutofill() {
  document.querySelectorAll('input[type="file"][data-autofill-target]').forEach((input) => {
    const targetId = input.dataset.autofillTarget;
    const target = document.getElementById(targetId);
    if (!target) return;
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (!file) return;
      const name = file.name.replace(/\.[^.]+$/, "") || file.name;
      if (target && !target.value.trim()) target.value = name;
    });
  });
}

function escapeHtml(text) {
  if (!text) return text;
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function formatTime(seconds) {
  if (!seconds || isNaN(seconds) || seconds === Infinity) return "00:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

window.adjustVolume = function(val) {
  const audio = document.querySelector('#room-audio');
  const icon = document.querySelector('#vol-icon');
  if (audio) {
    audio.volume = val;
    if (val == 0) icon.className = 'ri-volume-mute-line';
    else if (val < 0.5) icon.className = 'ri-volume-down-line';
    else icon.className = 'ri-volume-up-line';
  }
};