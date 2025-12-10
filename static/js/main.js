document.addEventListener("DOMContentLoaded", () => {
  initSliderVerification();
  initRoomSync();
  initMusicAutofill();
});

// --- 1. 滑块验证逻辑 (保持不变) ---
function initSliderVerification() {
  document.querySelectorAll(".slider-verify").forEach((wrapper) => {
    const thumb = wrapper.querySelector(".slider-thumb");
    const track = wrapper.querySelector(".slider-track");
    const tip = wrapper.querySelector(".slider-tip");
    const hiddenInputId = wrapper.dataset.target;
    const hiddenInput = document.getElementById(hiddenInputId);

    if (!thumb || !track || !hiddenInput) return;

    let isDragging = false;
    let startX = 0;
    let currentX = 0;
    const maxOffset = track.offsetWidth - thumb.offsetWidth - 8;

    function setVerified() {
      hiddenInput.value = "verified";
      tip.textContent = "验证完成";
      track.classList.add("verified");
    }

    function resetSlider() {
      hiddenInput.value = "";
      thumb.style.transform = "translateX(0px)";
      tip.textContent = "拖动滑块完成验证";
      track.classList.remove("verified");
    }

    const onPointerDown = (event) => {
      isDragging = true;
      startX = event.clientX || event.touches?.[0]?.clientX;
      thumb.setPointerCapture(event.pointerId || 1);
    };

    const onPointerMove = (event) => {
      if (!isDragging) return;
      const clientX = event.clientX || event.touches?.[0]?.clientX;
      const diff = clientX - startX;
      currentX = Math.min(Math.max(0, diff), maxOffset);
      thumb.style.transform = `translateX(${currentX}px)`;
      if (currentX >= maxOffset) {
        isDragging = false;
        setVerified();
      }
    };

    const onPointerUp = (event) => {
      if (!isDragging) return;
      isDragging = false;
      if (currentX < maxOffset) {
        resetSlider();
      } else {
        setVerified();
      }
      thumb.releasePointerCapture(event.pointerId || 1);
    };

    thumb.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    resetSlider();
  });
}

// --- 2. 房间同步核心逻辑 (修复绿灯和进度条) ---
function initRoomSync() {
  if (!window.roomConfig) return;

  const { stateUrl, audioSelector } = window.roomConfig;
  const audio = document.querySelector(audioSelector);

  // UI 元素
  const label = document.querySelector("#state-label");
  const trackLabel = document.querySelector("#current-track-label");
  const statusIndicator = document.querySelector(".status-indicator");
  // 【修复点 1】获取绿灯元素
  const statusDot = document.querySelector(".status-dot");
  const chatLog = document.querySelector("#chat-log");

  // 进度条元素
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

  // 轮询同步状态
  async function refreshState() {
    try {
      const response = await fetch(stateUrl);
      if (!response.ok) return;
      const state = await response.json();

      // 1. 更新 UI 文本和状态
      if (label) {
        label.textContent = state.playback_status === "playing" ? "播放中" : "已暂停";
      }

      // 【修复点 2】更新绿灯状态
      if (statusDot) {
        // 清除旧状态，强制添加新状态
        statusDot.classList.remove('playing', 'paused');
        statusDot.classList.add(state.playback_status);
      }

      if (trackLabel) {
        const newTitle = state.current_track_name || "等待播放...";
        if (trackLabel.textContent.trim() !== newTitle) {
           trackLabel.textContent = newTitle;
        }
      }

      if (statusIndicator) {
        statusIndicator.textContent = state.is_active ? "正在营业" : "已打烊";
        statusIndicator.className = `status-indicator ${state.is_active ? 'active' : 'closed'}`;
      }

      // 2. 音频播放同步
      if (audio && state.is_active) {
          if (state.current_track_file) {
            const targetSrc = `/static/uploads/music/${state.current_track_file}`;
            const currentSrcPath = decodeURIComponent(audio.src).split('/static/uploads/music/')[1];

            // 切歌逻辑
            if (currentSrcPath !== state.current_track_file) {
              console.log("切歌同步:", state.current_track_name);
              audio.src = targetSrc;
              try {
                  await audio.load();
                  if (state.playback_status === "playing") {
                      const playPromise = audio.play();
                      if (playPromise !== undefined) {
                          playPromise.catch(error => {
                              console.log("自动播放被拦截，需要用户交互:", error);
                          });
                      }
                  }
              } catch (e) { console.error(e); }
            }

            // 状态同步
            if (state.playback_status === "playing") {
                if (audio.paused) {
                    const playPromise = audio.play();
                    if (playPromise !== undefined) {
                        playPromise.catch(error => {
                            // 此时进度条不会走，因为被浏览器拦截了
                            console.log("等待用户点击以开始播放");
                        });
                    }
                }
                // 同步黑胶动画
                if (vinylWrapper) vinylWrapper.classList.add('spinning');
            } else {
                if (!audio.paused) audio.pause();
                if (vinylWrapper) vinylWrapper.classList.remove('spinning');
            }
          }
      }

      // 3. 聊天同步
      if (chatLog && state.messages) {
          updateChatLog(chatLog, state.messages);
      }

    } catch (error) {
      console.error("Sync error:", error);
    }
  }

  refreshState();
  setInterval(refreshState, 2000);
}

// --- 3. 聊天记录更新 (保持不变) ---
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
                        <div class="chat-bubble">
                            ${escapeHtml(msg.content)}
                        </div>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
            hasNew = true;
        }
    });

    if (hasNew) {
         container.scrollTop = container.scrollHeight;
    }
}

// --- 4. 辅助函数 (保持不变) ---
function initMusicAutofill() {
  document.querySelectorAll('input[type="file"][data-autofill-target]').forEach((input) => {
    const targetId = input.dataset.autofillTarget;
    const target = document.getElementById(targetId);
    if (!target) return;
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (!file) return;
      const name = file.name.replace(/\.[^.]+$/, "") || file.name;
      if (target && !target.value.trim()) {
          target.value = name;
      }
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