/**
 * 七夕节送祝福 - 主应用逻辑
 */

document.addEventListener('DOMContentLoaded', () => {
  // --- STATE ---
  const state = {
    to: '亲爱的你',
    from: '一位特别的人',
    msg: '纤云弄巧，飞星传恨，银汉迢迢暗度。\n金风玉露一相逢，便胜却人间无数。',
    theme: 'starry', // starry, rose, vintage, aurora
    isAudioPlaying: false,
    audioCtx: null,
    audioTimer: null
  };

  // --- DOM ELEMENTS ---
  const bgCanvas = document.getElementById('bgCanvas');
  const ctx = bgCanvas.getContext('2d');

  const createSection = document.getElementById('createSection');
  const viewSection = document.getElementById('viewSection');

  const inputTo = document.getElementById('inputTo');
  const inputFrom = document.getElementById('inputFrom');
  const inputMsg = document.getElementById('inputMsg');
  const themePills = document.querySelectorAll('.theme-pill');

  const previewFrame = document.getElementById('previewFrame');
  const previewTo = document.getElementById('previewTo');
  const previewMsg = document.getElementById('previewMsg');
  const previewFrom = document.getElementById('previewFrom');

  const envelope = document.getElementById('envelope');
  const envelopeSeal = document.getElementById('envelopeSeal');
  const revealedCard = document.getElementById('revealedCard');
  const viewFrame = document.getElementById('viewFrame');
  const viewTo = document.getElementById('viewTo');
  const viewMsg = document.getElementById('viewMsg');
  const viewFrom = document.getElementById('viewFrom');

  const btnGenerateLink = document.getElementById('btnGenerateLink');
  const btnDownloadCard = document.getElementById('btnDownloadCard');
  const btnReleaseLantern = document.getElementById('btnReleaseLantern');
  const btnCreateNew = document.getElementById('btnCreateNew');
  const btnToggleAudio = document.getElementById('btnToggleAudio');

  const shareModal = document.getElementById('shareModal');
  const modalClose = document.getElementById('modalClose');
  const shareLinkInput = document.getElementById('shareLinkInput');
  const btnCopyShareLink = document.getElementById('btnCopyShareLink');
  const toastContainer = document.getElementById('toastContainer');

  // --- INITIALIZATION ---
  initCanvas();
  checkUrlParams();
  bindEvents();
  renderPresetTags();

  // --- CANVAS PARTICLE & LANTERN ENGINE ---
  let width = (bgCanvas.width = window.innerWidth);
  let height = (bgCanvas.height = window.innerHeight);

  const stars = [];
  const shootingStars = [];
  const lanterns = [];

  // Generate initial stars
  for (let i = 0; i < 120; i++) {
    stars.push({
      x: Math.random() * width,
      y: Math.random() * height,
      radius: Math.random() * 1.5 + 0.5,
      alpha: Math.random(),
      speed: Math.random() * 0.02 + 0.005
    });
  }

  function initCanvas() {
    window.addEventListener('resize', () => {
      width = bgCanvas.width = window.innerWidth;
      height = bgCanvas.height = window.innerHeight;
    });
    requestAnimationFrame(renderCanvas);
  }

  function renderCanvas() {
    ctx.clearRect(0, 0, width, height);

    // 1. Draw twinkling stars
    stars.forEach(star => {
      star.alpha += star.speed;
      if (star.alpha > 1 || star.alpha < 0) star.speed = -star.speed;
      ctx.beginPath();
      ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255, 255, 255, ${Math.abs(star.alpha)})`;
      ctx.shadowBlur = star.radius * 2;
      ctx.shadowColor = '#fff';
      ctx.fill();
    });

    // 2. Random Shooting Star
    if (Math.random() < 0.015 && shootingStars.length < 3) {
      shootingStars.push({
        x: Math.random() * width,
        y: Math.random() * (height / 2),
        len: Math.random() * 80 + 50,
        speed: Math.random() * 6 + 4,
        alpha: 1
      });
    }

    shootingStars.forEach((star, index) => {
      ctx.beginPath();
      const grad = ctx.createLinearGradient(star.x, star.y, star.x - star.len, star.y + star.len);
      grad.addColorStop(0, `rgba(255, 255, 255, ${star.alpha})`);
      grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
      ctx.strokeStyle = grad;
      ctx.lineWidth = 2;
      ctx.moveTo(star.x, star.y);
      ctx.lineTo(star.x - star.len, star.y + star.len);
      ctx.stroke();

      star.x += star.speed;
      star.y += star.speed;
      star.alpha -= 0.015;

      if (star.alpha <= 0) shootingStars.splice(index, 1);
    });

    // 3. Sky Lanterns
    lanterns.forEach((lantern, index) => {
      lantern.y -= lantern.speedY;
      lantern.x += Math.sin(lantern.y * 0.02) * 0.5;
      lantern.alpha = Math.min(1, lantern.y / 200);

      ctx.save();
      ctx.translate(lantern.x, lantern.y);

      // Glow
      ctx.shadowBlur = 15;
      ctx.shadowColor = 'rgba(255, 183, 94, 0.8)';

      // Lantern Body
      ctx.beginPath();
      ctx.fillStyle = 'rgba(255, 140, 50, 0.85)';
      ctx.moveTo(-lantern.size, -lantern.size * 1.2);
      ctx.quadraticCurveTo(0, -lantern.size * 1.6, lantern.size, -lantern.size * 1.2);
      ctx.lineTo(lantern.size * 0.8, lantern.size);
      ctx.lineTo(-lantern.size * 0.8, lantern.size);
      ctx.closePath();
      ctx.fill();

      // Flame core
      ctx.beginPath();
      ctx.arc(0, lantern.size * 0.5, lantern.size * 0.3, 0, Math.PI * 2);
      ctx.fillStyle = '#fff7b2';
      ctx.fill();

      ctx.restore();

      if (lantern.y < -50) lanterns.splice(index, 1);
    });

    requestAnimationFrame(renderCanvas);
  }

  function addLantern(x, y) {
    lanterns.push({
      x: x || Math.random() * (width - 100) + 50,
      y: y || height + 20,
      size: Math.random() * 10 + 12,
      speedY: Math.random() * 1.2 + 0.8,
      alpha: 1
    });
  }

  // Auto spawn ambient lanterns periodically
  setInterval(() => {
    if (lanterns.length < 8) addLantern();
  }, 3500);

  // --- PRESET TAGS RENDERER ---
  function renderPresetTags() {
    const container = document.getElementById('presetTags');
    if (!container) return;

    const categories = [
      { name: '经典诗词', list: PRESET_WISHES.poetry },
      { name: '浪漫告白', list: PRESET_WISHES.romantic },
      { name: '甜蜜祝福', list: PRESET_WISHES.sweet },
      { name: '趣味问候', list: PRESET_WISHES.fun }
    ];

    container.innerHTML = '';
    categories.forEach(cat => {
      cat.list.forEach((text, i) => {
        const btn = document.createElement('button');
        btn.className = 'tag-btn';
        btn.innerText = `${cat.name} ${i + 1}`;
        btn.onclick = () => {
          inputMsg.value = text;
          updatePreview();
          showToast(`已套用：${cat.name}`);
        };
        container.appendChild(btn);
      });
    });
  }

  // --- REALTIME PREVIEW UPDATE ---
  function updatePreview() {
    state.to = inputTo.value.trim() || '特别的你';
    state.from = inputFrom.value.trim() || '为你祝福的人';
    state.msg = inputMsg.value.trim() || '愿得一人心，白首不相离。七夕快乐！';

    previewTo.innerText = `致 ${state.to}：`;
    previewMsg.innerText = state.msg;
    previewFrom.innerText = `—— ${state.from}`;

    previewFrame.className = `card-preview-frame theme-${state.theme}`;
    if (viewFrame) viewFrame.className = `card-preview-frame theme-${state.theme}`;
  }

  // --- URL ENCODING & ROUTING ---
  function checkUrlParams() {
    const hash = window.location.hash.substring(1);
    const searchParams = new URLSearchParams(window.location.search);
    const bData = searchParams.get('b') || hash;

    if (bData) {
      try {
        const decoded = JSON.parse(decodeURIComponent(escape(atob(bData))));
        state.to = decoded.t || '特别的你';
        state.from = decoded.f || '为你祝福的人';
        state.msg = decoded.m || '七夕快乐！';
        state.theme = decoded.s || 'starry';

        showSection('view');
        setupViewCard();
        return;
      } catch (e) {
        console.error('Invalid URL data format', e);
      }
    }
    showSection('create');
    updatePreview();
  }

  function generateShareUrl() {
    const dataObj = {
      t: state.to,
      f: state.from,
      m: state.msg,
      s: state.theme
    };
    const jsonStr = JSON.stringify(dataObj);
    const base64Str = btoa(unescape(encodeURIComponent(jsonStr)));
    
    // Construct clean URL
    const baseUrl = window.location.origin + window.location.pathname;
    return `${baseUrl}?b=${encodeURIComponent(base64Str)}`;
  }

  function showSection(name) {
    if (name === 'create') {
      createSection.classList.add('active');
      viewSection.classList.remove('active');
    } else {
      createSection.classList.remove('active');
      viewSection.classList.add('active');
    }
  }

  // --- VIEW CARD & UNSEAL ENVELOPE ---
  function setupViewCard() {
    viewTo.innerText = `致 ${state.to}：`;
    viewFrom.innerText = `—— ${state.from}`;
    if (viewFrame) viewFrame.className = `card-preview-frame theme-${state.theme}`;
  }

  function openEnvelope() {
    if (envelope.classList.contains('opened')) return;

    envelope.classList.add('opened');
    playToneSequence();

    // Release 5 lanterns!
    for (let i = 0; i < 5; i++) {
      setTimeout(() => addLantern(), i * 300);
    }

    setTimeout(() => {
      envelope.style.display = 'none';
      revealedCard.style.display = 'block';
      typewriterEffect(viewMsg, state.msg);
    }, 700);
  }

  function typewriterEffect(element, text) {
    element.innerHTML = '';
    let index = 0;
    const timer = setInterval(() => {
      if (index < text.length) {
        element.innerHTML += text.charAt(index) === '\n' ? '<br>' : text.charAt(index);
        index++;
      } else {
        clearInterval(timer);
      }
    }, 60);
  }

  // --- IMAGE CARD EXPORT (CANVAS) ---
  function downloadCardImage() {
    const canvas = document.createElement('canvas');
    canvas.width = 800;
    canvas.height = 1000;
    const ctx2d = canvas.getContext('2d');

    // Theme Background Gradients
    let bgGrad;
    if (state.theme === 'rose') {
      bgGrad = ctx2d.createLinearGradient(0, 0, 800, 1000);
      bgGrad.addColorStop(0, '#2b0b1e');
      bgGrad.addColorStop(0.5, '#4a122e');
      bgGrad.addColorStop(1, '#1a0410');
    } else if (state.theme === 'vintage') {
      bgGrad = ctx2d.createLinearGradient(0, 0, 800, 1000);
      bgGrad.addColorStop(0, '#2a1f14');
      bgGrad.addColorStop(0.5, '#3e2815');
      bgGrad.addColorStop(1, '#150d06');
    } else if (state.theme === 'aurora') {
      bgGrad = ctx2d.createLinearGradient(0, 0, 800, 1000);
      bgGrad.addColorStop(0, '#071e2e');
      bgGrad.addColorStop(0.5, '#0e3b43');
      bgGrad.addColorStop(1, '#020e17');
    } else {
      bgGrad = ctx2d.createLinearGradient(0, 0, 800, 1000);
      bgGrad.addColorStop(0, '#100b2b');
      bgGrad.addColorStop(0.5, '#201047');
      bgGrad.addColorStop(1, '#0d0324');
    }

    ctx2d.fillStyle = bgGrad;
    ctx2d.fillRect(0, 0, 800, 1000);

    // Decorative Border
    ctx2d.strokeStyle = 'rgba(255, 215, 0, 0.4)';
    ctx2d.lineWidth = 6;
    ctx2d.strokeRect(30, 30, 740, 940);

    // Title Ornament
    ctx2d.font = '36px "Noto Serif SC", serif';
    ctx2d.fillStyle = '#ffd700';
    ctx2d.textAlign = 'center';
    ctx2d.fillText('✦  七夕·星河倾心  ✦', 400, 120);

    // To:
    ctx2d.font = 'bold 34px "Noto Serif SC", serif';
    ctx2d.fillStyle = '#ff4b8b';
    ctx2d.textAlign = 'left';
    ctx2d.fillText(`致 ${state.to}：`, 80, 220);

    // Message Body Text (word wrap)
    ctx2d.font = '28px "Noto Serif SC", serif';
    ctx2d.fillStyle = '#f8fafc';
    const lines = state.msg.split('\n');
    let startY = 300;

    lines.forEach(line => {
      ctx2d.fillText(line, 80, startY);
      startY += 50;
    });

    // From:
    ctx2d.font = 'bold 30px "Noto Serif SC", serif';
    ctx2d.fillStyle = '#ffd700';
    ctx2d.textAlign = 'right';
    ctx2d.fillText(`—— ${state.from}`, 720, Math.max(startY + 60, 820));

    // Footer Watermark
    ctx2d.font = '18px sans-serif';
    ctx2d.fillStyle = 'rgba(255, 255, 255, 0.4)';
    ctx2d.textAlign = 'center';
    ctx2d.fillText('七夕专属祝福卡片 · 无需登录极简生成', 400, 930);

    // Download trigger
    const image = canvas.toDataURL('image/png');
    const link = document.createElement('a');
    link.download = `七夕祝福_${state.to}.png`;
    link.href = image;
    link.click();

    showToast('祝福卡片图片已导出！');
  }

  // --- WEB AUDIO API SOFT MUSIC SYNTHESIS ---
  function toggleAudio() {
    if (state.isAudioPlaying) {
      stopAudio();
    } else {
      startAudio();
    }
  }

  function startAudio() {
    if (!state.audioCtx) {
      state.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (state.audioCtx.state === 'suspended') {
      state.audioCtx.resume();
    }

    state.isAudioPlaying = true;
    btnToggleAudio.classList.add('active');
    btnToggleAudio.querySelector('span:nth-child(2)').innerText = '背景音乐：开';

    // Pentatonic chime notes (C5, D5, E5, G5, A5, C6)
    const notes = [523.25, 587.33, 659.25, 783.99, 880.00, 1046.50];
    state.audioTimer = setInterval(() => {
      if (!state.isAudioPlaying) return;
      const note = notes[Math.floor(Math.random() * notes.length)];
      playSineTone(note, 2.5);
    }, 1800);

    showToast('已开启七夕浪漫音效');
  }

  function stopAudio() {
    state.isAudioPlaying = false;
    if (state.audioTimer) clearInterval(state.audioTimer);
    btnToggleAudio.classList.remove('active');
    btnToggleAudio.querySelector('span:nth-child(2)').innerText = '背景音乐：关';
    showToast('背景音乐已暂停');
  }

  function playSineTone(freq, duration) {
    if (!state.audioCtx) return;
    try {
      const osc = state.audioCtx.createOscillator();
      const gain = state.audioCtx.createGain();

      osc.type = 'sine';
      osc.frequency.value = freq;

      gain.gain.setValueAtTime(0.001, state.audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.12, state.audioCtx.currentTime + 0.3);
      gain.gain.exponentialRampToValueAtTime(0.001, state.audioCtx.currentTime + duration);

      osc.connect(gain);
      gain.connect(state.audioCtx.destination);

      osc.start();
      osc.stop(state.audioCtx.currentTime + duration);
    } catch (e) {
      console.error(e);
    }
  }

  function playToneSequence() {
    if (!state.audioCtx) {
      state.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    const notes = [523.25, 659.25, 783.99, 1046.50];
    notes.forEach((freq, i) => {
      setTimeout(() => playSineTone(freq, 2.0), i * 220);
    });
  }

  // --- EVENT BINDINGS ---
  function bindEvents() {
    inputTo.addEventListener('input', updatePreview);
    inputFrom.addEventListener('input', updatePreview);
    inputMsg.addEventListener('input', updatePreview);

    themePills.forEach(pill => {
      pill.addEventListener('click', () => {
        themePills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        state.theme = pill.dataset.theme;
        updatePreview();
      });
    });

    btnGenerateLink.addEventListener('click', () => {
      const shareUrl = generateShareUrl();
      shareLinkInput.value = shareUrl;
      shareModal.classList.add('active');
    });

    btnDownloadCard.addEventListener('click', downloadCardImage);

    btnCopyShareLink.addEventListener('click', () => {
      copyToClipboard(shareLinkInput.value);
      showToast('链接已复制，快去发给 TA 吧！');
      shareModal.classList.remove('active');
    });

    modalClose.addEventListener('click', () => {
      shareModal.classList.remove('active');
    });

    envelopeSeal.addEventListener('click', openEnvelope);
    envelope.addEventListener('click', openEnvelope);

    btnReleaseLantern.addEventListener('click', (e) => {
      for (let i = 0; i < 4; i++) {
        setTimeout(() => addLantern(e.clientX + (Math.random() * 60 - 30)), i * 200);
      }
      playSineTone(783.99, 1.5);
      showToast('许愿天灯已放飞 ✨');
    });

    btnCreateNew.addEventListener('click', () => {
      window.location.href = window.location.pathname;
    });

    btnToggleAudio.addEventListener('click', toggleAudio);
  }

  // --- UTILS: TOAST & COPY ---
  function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text);
    } else {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
    }
  }

  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<span>💖</span> <span>${message}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.4s ease';
      setTimeout(() => toast.remove(), 400);
    }, 2500);
  }
});
