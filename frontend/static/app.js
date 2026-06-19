// ═══════════════════════════════════════════════════════════════
// Antigravity IDE — Client Application
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {

  // ── Application State ──
  const state = {
    tools: [],
    categories: { Communication: true, Planning: true, Content: true, Supervisor: true },
    configs: {},
    ttsEnabled: true,
    isListening: false,
    isSpeaking: false,
    isProcessing: false,
    voiceModeActive: false,
    recognition: null,
    selectedVoice: null,
    threadId: 'session_' + Math.random().toString(36).substring(2, 15),
    currentModel: 'gpt-4.1-mini',
  };

  // ── DOM References ──
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const chatContainer   = $('#chat-container');
  const chatInput        = $('#chat-input');
  const btnSend          = $('#btn-send');
  const btnMic           = $('#btn-mic');
  const btnVoiceToggle   = $('#btn-voice-toggle');
  const modelBadge       = $('#model-badge');
  const voiceIndicator   = $('#voice-indicator');
  const btnNewChat       = $('#btn-new-chat');
  const btnAgentMenu     = $('#btn-agent-menu');
  const agentDropdown    = $('#agent-dropdown');
  const btnCloseAgent    = $('#btn-close-agent');
  const agentPanel       = $('#agent-panel');
  const btnOpenSettings  = $('#btn-open-settings');
  const btnSaveSettings  = $('#btn-save-settings');
  const bottomPanel      = $('#bottom-panel');
  const terminalOut      = $('#terminal-output');
  const voiceOverlay     = $('#voice-overlay');
  const voOrb            = $('#vo-orb');
  const voLabel          = $('#vo-label');
  const voSub            = $('#vo-sub');
  const voWaves          = $('#vo-waves');

  // ═══════════════════════════════════════════════════════════
  // 1. LEFT SIDEBAR — Accordion & File Tree
  // ═══════════════════════════════════════════════════════════

  // Section toggles
  $$('.sb-section-head').forEach(head => {
    head.addEventListener('click', () => {
      const targetId = head.dataset.toggle;
      const body = document.getElementById(targetId);
      const section = head.closest('.sb-section');
      if (!body) return;
      
      if (body.classList.contains('collapsed')) {
        body.classList.remove('collapsed');
        section.classList.add('open');
      } else {
        body.classList.add('collapsed');
        section.classList.remove('open');
      }
    });
  });

  // Folder toggles
  $$('.tree-node.folder').forEach(node => {
    node.addEventListener('click', () => {
      const targetId = node.dataset.toggle;
      const children = document.getElementById(targetId);
      if (!children) return;
      
      if (children.classList.contains('collapsed')) {
        children.classList.remove('collapsed');
        node.classList.add('open');
      } else {
        children.classList.add('collapsed');
        node.classList.remove('open');
      }
    });
  });

  // ═══════════════════════════════════════════════════════════
  // 2. EDITOR TABS
  // ═══════════════════════════════════════════════════════════

  window.switchTab = function(name) {
    // Tabs
    $$('.tab').forEach(t => t.classList.remove('active'));
    const tab = $(`#tab-${name}`);
    if (tab) { tab.style.display = 'flex'; tab.classList.add('active'); }

    // Panes
    $$('.pane').forEach(p => p.classList.remove('active'));
    const pane = $(`#pane-${name}`);
    if (pane) pane.classList.add('active');

    // File tree highlighting
    $$('.tree-node.file').forEach(n => n.classList.remove('active'));
    const treeMap = { welcome: 'Welcome.md', settings: 'settings.json' };
    $$('.tree-node.file').forEach(n => {
      if (n.textContent.trim().includes(treeMap[name] || '')) n.classList.add('active');
    });

    tlog(`Switched to tab: ${name}`, 'info');
  };

  window.closeTab = function(name) {
    const tab = $(`#tab-${name}`);
    if (tab) tab.style.display = 'none';
    switchTab('welcome');
  };

  // Settings shortcut
  btnOpenSettings.addEventListener('click', () => switchTab('settings'));

  // ═══════════════════════════════════════════════════════════
  // 3. BOTTOM PANEL
  // ═══════════════════════════════════════════════════════════

  $$('.bp-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      $$('.bp-tab').forEach(t => t.classList.remove('active'));
      $$('.bp-pane').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const pane = $(`#bp-${tab.dataset.bp}`);
      if (pane) pane.classList.add('active');
      
      // Expand if collapsed
      bottomPanel.classList.remove('collapsed');
    });
  });

  $('#bp-maximize').addEventListener('click', () => bottomPanel.classList.toggle('maximized'));
  $('#bp-close').addEventListener('click', () => bottomPanel.classList.toggle('collapsed'));

  // Terminal Logger
  function tlog(msg, level = 'dim') {
    if (!terminalOut) return;
    const now = new Date().toISOString().replace('T', ' ').substring(0, 19);
    const labels = { dim: 'INFO ', info: 'INFO ', ok: 'OK   ', warn: 'WARN ', err: 'ERROR' };
    const line = document.createElement('div');
    line.className = `t-line ${level}`;
    line.textContent = `${now} | ${labels[level] || 'INFO '} | ${msg}`;
    terminalOut.appendChild(line);
    const bp = $('#bp-terminal');
    if (bp) bp.scrollTop = bp.scrollHeight;
  }

  // ═══════════════════════════════════════════════════════════
  // 4. AGENT PANEL — Dropdown & Tools Menu
  // ═══════════════════════════════════════════════════════════

  // Toggle main dropdown
  btnAgentMenu.addEventListener('click', e => {
    e.stopPropagation();
    agentDropdown.classList.toggle('open');
  });
  document.addEventListener('click', () => agentDropdown.classList.remove('open'));
  agentDropdown.addEventListener('click', e => e.stopPropagation());

  // Clear chat
  $('#dd-clear').addEventListener('click', () => {
    resetChat();
    agentDropdown.classList.remove('open');
  });

  // Open settings from dropdown
  $('#dd-open-settings').addEventListener('click', () => {
    switchTab('settings');
    agentDropdown.classList.remove('open');
  });

  // Close agent panel
  btnCloseAgent.addEventListener('click', () => {
    agentPanel.classList.toggle('hidden');
    tlog('Agent panel toggled.', 'info');
  });

  // New chat
  btnNewChat.addEventListener('click', () => resetChat());

  function resetChat() {
    state.threadId = 'session_' + Math.random().toString(36).substring(2, 15);
    chatContainer.innerHTML = '';
    addMsg('JARVIS', `New session started. Thread: <code>${state.threadId.substring(0, 12)}…</code>`, 'agent');
    tlog(`Reset chat → ${state.threadId}`, 'ok');
    toast('Chat session reset.', 'info');
  }

  // ═══════════════════════════════════════════════════════════
  // 5. LOAD TOOLS & RENDER IN DROPDOWN
  // ═══════════════════════════════════════════════════════════

  async function loadTools() {
    try {
      const res = await fetch('/api/tools');
      const data = await res.json();
      state.tools = data.tools || [];
      state.categories = data.categories || state.categories;
      renderToolsDropdown();
      tlog(`Loaded ${state.tools.length} local tools in-process.`, 'ok');
    } catch (e) {
      tlog('Failed to load tools: ' + e.message, 'err');
      toast('Could not load tools configuration.', 'error');
    }
  }

  function renderToolsDropdown() {
    const containers = {
      Communication: $('#tl-Communication'),
      Planning: $('#tl-Planning'),
      Content: $('#tl-Content'),
      Supervisor: $('#tl-Supervisor'),
    };

    Object.values(containers).forEach(c => { if (c) c.innerHTML = ''; });

    state.tools.forEach(tool => {
      const catEnabled = state.categories[tool.category] !== false;
      const container = containers[tool.category];
      if (!container) return;

      const row = document.createElement('label');
      row.className = 'tool-row';
      row.innerHTML = `
        <input type="checkbox" ${tool.enabled ? 'checked' : ''} ${catEnabled ? '' : 'disabled'} data-tool="${tool.name}">
        <div class="tool-info">
          <span class="tool-name">${tool.name}</span>
          <span class="tool-desc">${tool.description}</span>
        </div>
      `;

      const cb = row.querySelector('input');
      cb.addEventListener('change', () => toggleTool(tool.name, cb.checked, cb));
      container.appendChild(row);
    });
  }

  async function toggleTool(name, enabled, cbEl) {
    tlog(`Tool toggle: ${name} → ${enabled ? 'ON' : 'OFF'}`, 'info');
    try {
      const res = await fetch('/api/tools/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, enabled }),
      });
      if (!res.ok) throw new Error('Server error');
      const t = state.tools.find(x => x.name === name);
      if (t) t.enabled = enabled;
      toast(`${name} ${enabled ? 'enabled' : 'disabled'}.`, 'success');
    } catch (e) {
      cbEl.checked = !enabled;
      tlog(`Toggle failed for ${name}: ${e.message}`, 'err');
      toast('Failed to update tool.', 'error');
    }
  }

  // ═══════════════════════════════════════════════════════════
  // 6. LOAD & SAVE SETTINGS
  // ═══════════════════════════════════════════════════════════

  const CFG_MAP = {
    MODEL_NAME:            'cfg-model-name',
    DEFAULT_THREAD_ID:     'cfg-thread-id',
    GOOGLE_PSE_API_KEY:    'cfg-goog-key',
    GOOGLE_PSE_ENGINE_ID:  'cfg-goog-engine',
    AZURE_AI_ENDPOINT:     'cfg-az-endpoint',
    AZURE_AI_CREDENTIAL:   'cfg-az-key',
    AZURE_API_VERSION:     'cfg-az-version',
  };

  async function loadConfig() {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      state.configs = data.config || {};
      
      // Populate form
      for (const [key, elId] of Object.entries(CFG_MAP)) {
        const el = document.getElementById(elId);
        if (el && state.configs[key] !== undefined) el.value = state.configs[key];
      }

      // Apply model badge
      if (state.configs.MODEL_NAME) {
        state.currentModel = state.configs.MODEL_NAME;
        modelBadge.textContent = state.currentModel;
      }

      // Apply thread ID
      if (state.configs.DEFAULT_THREAD_ID) {
        state.threadId = state.configs.DEFAULT_THREAD_ID;
      }
      
      tlog('Configuration loaded from .env', 'ok');
    } catch (e) {
      tlog('Failed to load config: ' + e.message, 'err');
      toast('Error loading configuration.', 'error');
    }
  }

  btnSaveSettings.addEventListener('click', async () => {
    btnSaveSettings.disabled = true;
    btnSaveSettings.textContent = 'Saving…';
    tlog('Saving configuration & reloading agent runtime…', 'info');

    const updated = {};
    for (const [key, elId] of Object.entries(CFG_MAP)) {
      const el = document.getElementById(elId);
      if (el) updated[key] = el.value.trim();
    }

    try {
      // Save config
      const r1 = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: updated }),
      });
      if (!r1.ok) throw new Error('Config save failed');
      tlog('.env file updated successfully.', 'ok');

      // Reload agent
      tlog('Recompiling LangGraph + reinitializing in-process tools…', 'info');
      const r2 = await fetch('/api/agent/reload', { method: 'POST' });
      if (!r2.ok) throw new Error('Agent reload failed');
      tlog('Agent runtime hot-reloaded.', 'ok');

      // Sync state
      state.configs = { ...state.configs, ...updated };
      if (updated.MODEL_NAME) {
        state.currentModel = updated.MODEL_NAME;
        modelBadge.textContent = state.currentModel;
      }
      if (updated.DEFAULT_THREAD_ID) state.threadId = updated.DEFAULT_THREAD_ID;

      toast('Settings saved & agent reloaded!', 'success');
    } catch (e) {
      tlog(`Save/Reload error: ${e.message}`, 'err');
      toast('Error: ' + e.message, 'error');
    } finally {
      btnSaveSettings.disabled = false;
      btnSaveSettings.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
        Save &amp; Reload Agent Runtime`;
    }
  });

  // ═══════════════════════════════════════════════════════════
  // 7. CHAT — Send & Render Messages
  // ═══════════════════════════════════════════════════════════

  async function submitMessage(query) {
    if (!query?.trim()) return;

    addMsg('You', query, 'user');
    state.isProcessing = true;
    updateVoiceUI('processing');
    tlog(`→ Sending: "${query.substring(0, 60)}…"`, 'info');

    if (state.voiceModeActive) {
      voLabel.textContent = 'Thinking…';
      voSub.textContent = `"${query.substring(0, 80)}"`;
    }

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, thread_id: state.threadId }),
      });
      const data = await res.json();
      state.isProcessing = false;

      if (data.thought_logs) addThoughts(data.thought_logs);
      addMsg('JARVIS', data.response, 'agent');
      tlog('← Response received.', 'ok');

      if (state.voiceModeActive || state.ttsEnabled) speakText(data.response);
      else updateVoiceUI('idle');
    } catch (e) {
      state.isProcessing = false;
      updateVoiceUI('idle');
      addMsg('System', 'Error: Could not reach the agent server.', 'system');
      tlog(`Chat error: ${e.message}`, 'err');
      if (state.voiceModeActive) {
        voLabel.textContent = 'Connection Error';
        voSub.textContent = 'Could not reach the server.';
      }
    }
  }

  function addMsg(sender, text, type) {
    const div = document.createElement('div');
    div.className = `msg ${type}`;

    const avatarLetter = type === 'user' ? 'Y' : type === 'agent' ? 'J' : '!';
    const formatted = parseMd(text);

    div.innerHTML = `
      <div class="msg-avatar">${avatarLetter}</div>
      <div class="msg-body">
        <div class="msg-name">${sender}</div>
        <div class="msg-text">${formatted}</div>
      </div>
    `;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  function addThoughts(text) {
    if (!text?.trim()) return;
    const div = document.createElement('div');
    div.className = 'thought-toggle';
    div.innerHTML = `
      <div class="thought-head">💡 Agent Thoughts &amp; Tool Calls <span>▼</span></div>
      <div class="thought-body" style="display:none">${esc(text)}</div>
    `;
    const head = div.querySelector('.thought-head');
    const body = div.querySelector('.thought-body');
    head.addEventListener('click', () => {
      const hidden = body.style.display === 'none';
      body.style.display = hidden ? 'block' : 'none';
      head.querySelector('span').textContent = hidden ? '▲' : '▼';
    });
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  // ═══════════════════════════════════════════════════════════
  // 8. SPEECH RECOGNITION (always-on approach)
  // ═══════════════════════════════════════════════════════════

  function initSpeech() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { tlog('Speech Recognition API not available.', 'warn'); return; }

    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = 'en-US';

    let silenceTimer = null;
    let accumulated = '';

    rec.onstart = () => {
      state.isListening = true;
      accumulated = '';
      updateVoiceUI('listening');
      btnMic.classList.add('listening');
      voLabel.textContent = 'Listening…';
      voSub.textContent = 'Speak now…';
      voiceIndicator.textContent = '🎙️ Listening';
      tlog('Microphone active — listening for speech.', 'info');
    };

    rec.onresult = (e) => {
      if (silenceTimer) clearTimeout(silenceTimer);
      let interim = '', final = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }
      if (final) accumulated += ' ' + final;
      const show = (accumulated + ' ' + interim).trim();
      if (show) voSub.textContent = show;

      if (show) {
        silenceTimer = setTimeout(() => {
          const speech = (accumulated + ' ' + interim).trim();
          if (speech) {
            rec.stop();
            submitMessage(speech);
            accumulated = '';
          }
        }, 1500);
      }
    };

    rec.onerror = (e) => {
      state.isListening = false;
      btnMic.classList.remove('listening');
      tlog(`Speech error: ${e.error}`, 'err');
      if (e.error === 'not-allowed') {
        voLabel.textContent = 'Mic Blocked';
        voSub.textContent = 'Allow microphone access in browser settings.';
      }
      updateVoiceUI('idle');
    };

    rec.onend = () => {
      state.isListening = false;
      btnMic.classList.remove('listening');
      if (silenceTimer) clearTimeout(silenceTimer);
      if (!state.isProcessing && !state.isSpeaking) {
        updateVoiceUI('idle');
        voiceIndicator.textContent = state.ttsEnabled ? '🔊 Voice On' : '🔇 Muted';
      }
    };

    state.recognition = rec;
  }

  function startListening() {
    if (!state.recognition) { toast('Speech recognition unavailable.', 'warning'); return; }
    try { state.recognition.start(); } catch (e) { /* already running */ }
  }

  function stopListening() {
    if (state.recognition) state.recognition.stop();
  }

  // Mic button → toggle listening
  btnMic.addEventListener('click', () => {
    if (state.isListening) stopListening();
    else startListening();
  });

  // Voice overlay (full immersion mode)
  function enterVoiceMode() {
    state.voiceModeActive = true;
    voiceOverlay.classList.add('active');
    updateVoiceUI('idle');
    voLabel.textContent = 'Voice Mode Active';
    voSub.textContent = 'Click the orb and speak to JARVIS';
    tlog('Voice immersion mode activated.', 'info');
    setTimeout(startListening, 400);
  }

  function exitVoiceMode() {
    state.voiceModeActive = false;
    voiceOverlay.classList.remove('active');
    stopListening();
    window.speechSynthesis.cancel();
    state.isSpeaking = false;
    state.isListening = false;
    updateVoiceUI('idle');
    tlog('Voice mode deactivated.', 'info');
  }

  // Long-press mic for full voice mode, single click for inline mic toggle
  let micHoldTimer = null;
  btnMic.addEventListener('mousedown', () => {
    micHoldTimer = setTimeout(() => {
      enterVoiceMode();
      micHoldTimer = null; // consumed by long press
    }, 600);
  });
  btnMic.addEventListener('mouseup', () => {
    if (micHoldTimer) { clearTimeout(micHoldTimer); micHoldTimer = null; }
  });

  voOrb.addEventListener('click', () => {
    if (state.isListening) stopListening();
    else if (state.isSpeaking) { window.speechSynthesis.cancel(); state.isSpeaking = false; updateVoiceUI('idle'); }
    else startListening();
  });

  $('#vo-close').addEventListener('click', exitVoiceMode);
  $('#vo-back-to-chat').addEventListener('click', () => { exitVoiceMode(); chatInput.focus(); });

  function updateVoiceUI(status) {
    voOrb.className = 'vo-orb';
    voWaves.classList.remove('active');

    if (status === 'listening') { voOrb.classList.add('listening'); }
    else if (status === 'processing') { voLabel.textContent = 'Thinking…'; }
    else if (status === 'speaking') { voOrb.classList.add('speaking'); voWaves.classList.add('active'); }
    else { voLabel.textContent = state.voiceModeActive ? 'Voice Mode Active' : 'Voice Mode Ready'; }
  }

  // ═══════════════════════════════════════════════════════════
  // 9. TEXT-TO-SPEECH
  // ═══════════════════════════════════════════════════════════

  function speakText(text) {
    if (!state.ttsEnabled && !state.voiceModeActive) return;
    window.speechSynthesis.cancel();

    const clean = text.replace(/[\#\*\_`\[\]\(\)\-\+\>\n]/g, ' ').replace(/\s+/g, ' ').trim();
    const utt = new SpeechSynthesisUtterance(clean);

    if (!state.selectedVoice) {
      const voices = window.speechSynthesis.getVoices();
      state.selectedVoice = voices.find(v => v.lang.startsWith('en') && /Google|Neural|Natural/.test(v.name)) || voices[0];
    }
    if (state.selectedVoice) utt.voice = state.selectedVoice;

    utt.onstart = () => { state.isSpeaking = true; updateVoiceUI('speaking'); voLabel.textContent = 'Speaking…'; };
    utt.onend = () => {
      state.isSpeaking = false;
      updateVoiceUI('idle');
      voiceIndicator.textContent = state.ttsEnabled ? '🔊 Voice On' : '🔇 Muted';
      if (state.voiceModeActive) {
        setTimeout(() => { if (state.voiceModeActive && !state.isListening && !state.isSpeaking) startListening(); }, 300);
      }
    };
    utt.onerror = () => { state.isSpeaking = false; updateVoiceUI('idle'); };

    window.speechSynthesis.speak(utt);
  }

  // Populate voice selector in settings
  window.speechSynthesis.onvoiceschanged = () => {
    const voices = window.speechSynthesis.getVoices();
    const sel = $('#cfg-voice');
    if (!sel) return;
    sel.innerHTML = '<option value="default">Default System Voice</option>';
    voices.forEach((v, i) => {
      if (v.lang.includes('en')) {
        const opt = document.createElement('option');
        opt.value = i;
        opt.textContent = `${v.name} (${v.lang})`;
        sel.appendChild(opt);
      }
    });
    sel.addEventListener('change', () => {
      state.selectedVoice = sel.value === 'default' ? null : window.speechSynthesis.getVoices()[parseInt(sel.value)];
    });
  };

  // TTS toggle
  btnVoiceToggle.addEventListener('click', () => {
    state.ttsEnabled = !state.ttsEnabled;
    btnVoiceToggle.classList.toggle('active', state.ttsEnabled);
    voiceIndicator.textContent = state.ttsEnabled ? '🔊 Voice On' : '🔇 Muted';
    if (!state.ttsEnabled) { window.speechSynthesis.cancel(); state.isSpeaking = false; }
    toast(state.ttsEnabled ? 'Voice output enabled.' : 'Voice output muted.', 'info');
  });

  // ═══════════════════════════════════════════════════════════
  // 10. CHAT INPUT HANDLING
  // ═══════════════════════════════════════════════════════════

  chatInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const v = chatInput.value.trim();
      if (v) { submitMessage(v); chatInput.value = ''; }
    }
  });

  btnSend.addEventListener('click', () => {
    const v = chatInput.value.trim();
    if (v) { submitMessage(v); chatInput.value = ''; }
  });

  // Auto-resize textarea
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 100) + 'px';
  });

  // ═══════════════════════════════════════════════════════════
  // 11. ACTIVITY BAR NAVIGATION
  // ═══════════════════════════════════════════════════════════

  $$('.ab-btn[data-view]').forEach(btn => {
    btn.addEventListener('click', () => {
      const wasActive = btn.classList.contains('active');
      $$('.ab-btn[data-view]').forEach(b => b.classList.remove('active'));
      
      const sidebar = $('#sidebar');
      if (wasActive) {
        sidebar.style.width = '0px';
        sidebar.style.minWidth = '0px';
        sidebar.style.borderRight = 'none';
      } else {
        btn.classList.add('active');
        sidebar.style.width = '';
        sidebar.style.minWidth = '';
        sidebar.style.borderRight = '';
      }
    });
  });

  // ═══════════════════════════════════════════════════════════
  // UTILITIES
  // ═══════════════════════════════════════════════════════════

  function esc(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
  }

  function parseMd(text) {
    let h = esc(text);
    h = h.replace(/^\*\s(.*)/gm, '<li>$1</li>');
    h = h.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    h = h.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    h = h.replace(/`(.*?)`/g, '<code>$1</code>');
    h = h.replace(/\n/g, '<br>');
    return h;
  }

  function toast(msg, type = 'info') {
    const container = $('#toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    el.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ'}</span><span class="toast-msg">${msg}</span>`;
    container.appendChild(el);

    setTimeout(() => {
      el.classList.add('fade-out');
      setTimeout(() => el.remove(), 300);
    }, 3500);
  }

  // ═══════════════════════════════════════════════════════════
  // BOOTSTRAP
  // ═══════════════════════════════════════════════════════════

  initSpeech();
  loadTools();
  loadConfig();
  btnVoiceToggle.classList.add('active');
  voiceIndicator.textContent = '🔊 Voice On';
  tlog('Antigravity IDE initialized. All systems online.', 'ok');
});
