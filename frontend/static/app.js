// JARVIS Web Dashboard Client Application

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    activeTab: 'tools', // 'tools' | 'settings'
    tools: [],
    configs: {},
    isListening: false,
    isSpeaking: false,
    isProcessing: false,
    voiceModeActive: false,
    recognition: null,
    speechSynthesisUtterance: null,
    selectedVoice: null,
    ttsEnabled: true,
    threadId: 'web_session_' + Math.random().toString(36).substring(2, 15),
  };

  // DOM Elements
  const tabs = document.querySelectorAll('.nav-tab');
  const configSections = document.querySelectorAll('.config-section');
  const saveBtn = document.getElementById('save-settings-btn');
  const chatContainer = document.getElementById('chat-container');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const voiceBtn = document.getElementById('voice-btn');
  const floatingVoiceBtn = document.getElementById('floating-voice-btn');
  const voiceOverlay = document.getElementById('voice-overlay');
  const largeVoiceCircle = document.getElementById('large-voice-circle');
  const voiceStatusText = document.getElementById('voice-status-text');
  const voiceSubtext = document.getElementById('voice-subtext');
  const closeVoiceBtn = document.getElementById('close-voice-btn');
  const textToggleVoiceBtn = document.getElementById('text-toggle-voice-btn');
  
  // Tab Switching
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      configSections.forEach(s => s.classList.remove('active'));
      
      tab.classList.add('active');
      const targetSection = document.getElementById(`${tab.dataset.tab}-section`);
      if (targetSection) targetSection.classList.add('active');
      state.activeTab = tab.dataset.tab;
    });
  });

  // Load Initial Tools and Configurations
  async function loadTools() {
    try {
      const response = await fetch('/api/tools');
      const data = await response.json();
      state.tools = data.tools;
      renderToolsList();
    } catch (err) {
      console.error('Error loading tools:', err);
      showNotification('Error loading tools', 'error');
    }
  }

  async function loadConfig() {
    try {
      const response = await fetch('/api/config');
      const data = await response.json();
      state.configs = data.config;
      populateSettingsForm();
    } catch (err) {
      console.error('Error loading config:', err);
      showNotification('Error loading configuration', 'error');
    }
  }

  // Render Tools Checklist grouped by category
  function renderToolsList() {
    const categories = {
      'Communication': document.getElementById('comm-tools-list'),
      'Planning': document.getElementById('planning-tools-list'),
      'Content': document.getElementById('content-tools-list'),
      'Supervisor': document.getElementById('supervisor-tools-list'),
      'Other': document.getElementById('other-tools-list')
    };

    // Clear previous lists
    Object.values(categories).forEach(container => {
      if (container) container.innerHTML = '';
    });

    state.tools.forEach(tool => {
      const card = document.createElement('div');
      card.className = `tool-card ${tool.enabled ? '' : 'disabled'}`;
      card.innerHTML = `
        <input type="checkbox" class="tool-checkbox" data-name="${tool.name}" ${tool.enabled ? 'checked' : ''}>
        <div class="tool-info">
          <div class="tool-name">${tool.name}</div>
          <div class="tool-desc">${tool.description}</div>
        </div>
      `;

      // Handle card click (except checkbox itself to avoid double-toggle)
      card.addEventListener('click', (e) => {
        if (e.target.tagName !== 'INPUT') {
          const checkbox = card.querySelector('.tool-checkbox');
          checkbox.checked = !checkbox.checked;
          handleToolToggle(tool.name, checkbox.checked, card);
        }
      });

      // Handle checkbox change directly
      const checkbox = card.querySelector('.tool-checkbox');
      checkbox.addEventListener('change', () => {
        handleToolToggle(tool.name, checkbox.checked, card);
      });

      const catContainer = categories[tool.category] || categories['Other'];
      if (catContainer) {
        catContainer.appendChild(card);
      }
    });
  }

  // Handle individual tool enable/disable
  async function handleToolToggle(toolName, isEnabled, cardElement) {
    if (isEnabled) {
      cardElement.classList.remove('disabled');
    } else {
      cardElement.classList.add('disabled');
    }

    try {
      await fetch('/api/tools/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: toolName, enabled: isEnabled })
      });
      
      // Update local state
      const tool = state.tools.find(t => t.name === toolName);
      if (tool) tool.enabled = isEnabled;
    } catch (err) {
      console.error('Error toggling tool:', err);
      showNotification('Failed to toggle tool state', 'error');
    }
  }

  // Populate settings form fields
  function populateSettingsForm() {
    const fields = ['MODEL_NAME', 'DEFAULT_THREAD_ID', 'GOOGLE_PSE_API_KEY', 'GOOGLE_PSE_ENGINE_ID', 'AZURE_AI_ENDPOINT', 'AZURE_AI_CREDENTIAL', 'AZURE_API_VERSION'];
    fields.forEach(field => {
      const input = document.getElementById(`config-${field.toLowerCase().replace(/_/g, '-')}`);
      if (input && state.configs[field] !== undefined) {
        input.value = state.configs[field];
      }
    });
    
    // Set local threadId if it exists in settings
    if (state.configs['DEFAULT_THREAD_ID']) {
      state.threadId = state.configs['DEFAULT_THREAD_ID'];
    }
  }

  // Save Settings and Reload Agent
  saveBtn.addEventListener('click', async () => {
    saveBtn.disabled = true;
    saveBtn.innerHTML = 'Saving & Reloading...';

    // Gather values
    const updatedConfigs = {};
    const fields = ['MODEL_NAME', 'DEFAULT_THREAD_ID', 'GOOGLE_PSE_API_KEY', 'GOOGLE_PSE_ENGINE_ID', 'AZURE_AI_ENDPOINT', 'AZURE_AI_CREDENTIAL', 'AZURE_API_VERSION'];
    
    fields.forEach(field => {
      const input = document.getElementById(`config-${field.toLowerCase().replace(/_/g, '-')}`);
      if (input) {
        updatedConfigs[field] = input.value.trim();
      }
    });

    try {
      // 1. Save config values to backend
      const configRes = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: updatedConfigs })
      });
      
      if (!configRes.ok) throw new Error('Failed to update config');

      // 2. Hot-reload the agent graph
      const reloadRes = await fetch('/api/agent/reload', {
        method: 'POST'
      });
      
      if (!reloadRes.ok) throw new Error('Failed to reload agent');

      // Update internal configs and session threadId
      state.configs = { ...state.configs, ...updatedConfigs };
      if (updatedConfigs['DEFAULT_THREAD_ID']) {
        state.threadId = updatedConfigs['DEFAULT_THREAD_ID'];
      }

      showNotification('Agent settings saved and reloaded successfully!', 'success');
    } catch (err) {
      console.error(err);
      showNotification('Error saving configuration: ' + err.message, 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.innerHTML = 'Save Settings & Reload';
    }
  });

  // Speech Recognition Setup (Web Speech API)
  function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('Web Speech API (Recognition) is not supported in this browser.');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true; // Use continuous mode to prevent abrupt cutoffs
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    let silenceTimer = null;
    let accumulatedTranscript = '';

    recognition.onstart = () => {
      state.isListening = true;
      accumulatedTranscript = '';
      updateVoiceWidgetUI('listening');
      voiceStatusText.textContent = 'Listening...';
      voiceSubtext.textContent = 'Say something...';
    };

    recognition.onresult = (event) => {
      // Clear silence timer on any activity
      if (silenceTimer) clearTimeout(silenceTimer);

      let interimTranscript = '';
      let currentFinal = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          currentFinal += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      if (currentFinal) {
        accumulatedTranscript += ' ' + currentFinal;
      }

      const showText = (accumulatedTranscript + ' ' + interimTranscript).trim();
      if (showText) {
        voiceSubtext.textContent = showText;
      }

      // If we got any speech, start the 1.5 second silence timer
      if (showText) {
        silenceTimer = setTimeout(() => {
          const finalSpeech = (accumulatedTranscript + ' ' + interimTranscript).trim();
          if (finalSpeech) {
            recognition.stop();
            submitMessage(finalSpeech);
            accumulatedTranscript = '';
          }
        }, 1500); // Wait 1.5 seconds of silence before submitting
      }
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      state.isListening = false;
      
      if (event.error === 'not-allowed') {
        voiceStatusText.textContent = 'Permission Blocked';
        voiceSubtext.textContent = 'Please allow microphone access in your browser.';
      } else {
        voiceStatusText.textContent = 'Error occurred';
        voiceSubtext.textContent = 'Please try speaking again.';
      }
      updateVoiceWidgetUI('idle');
    };

    recognition.onend = () => {
      state.isListening = false;
      if (silenceTimer) clearTimeout(silenceTimer);
      if (!state.isProcessing && !state.isSpeaking) {
        updateVoiceWidgetUI('idle');
      }
    };

    state.recognition = recognition;
  }

  // Speech Synthesis (Text to Speech)
  function speakText(text) {
    if (!state.ttsEnabled) return;
    
    // Stop any ongoing speech
    window.speechSynthesis.cancel();

    // Clean markdown before speaking
    const cleanText = text.replace(/[\#\*\_`\[\]\(\)\-\+\>\n]/g, ' ').replace(/\s+/g, ' ').trim();
    
    const utterance = new SpeechSynthesisUtterance(cleanText);
    
    // Pick an English neural-sounding voice if available
    if (!state.selectedVoice) {
      const voices = window.speechSynthesis.getVoices();
      state.selectedVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Neural'))) || voices[0];
    }
    
    if (state.selectedVoice) {
      utterance.voice = state.selectedVoice;
    }

    utterance.onstart = () => {
      state.isSpeaking = true;
      updateVoiceWidgetUI('speaking');
      voiceStatusText.textContent = 'Speaking...';
    };

    utterance.onend = () => {
      state.isSpeaking = false;
      updateVoiceWidgetUI('idle');
      if (state.voiceModeActive) {
        // Automatically start listening again after speaking in voice mode
        setTimeout(() => {
          if (state.voiceModeActive && !state.isListening && !state.isSpeaking) {
            startListening();
          }
        }, 300);
      }
    };

    utterance.onerror = (e) => {
      console.error('Speech synthesis error:', e);
      state.isSpeaking = false;
      updateVoiceWidgetUI('idle');
    };

    state.speechSynthesisUtterance = utterance;
    window.speechSynthesis.speak(utterance);
  }

  // Populate voices list when they are loaded
  window.speechSynthesis.onvoiceschanged = () => {
    const voices = window.speechSynthesis.getVoices();
    const voiceSelect = document.getElementById('config-voice-select');
    if (voiceSelect) {
      voiceSelect.innerHTML = '<option value="default">Default System Voice</option>';
      voices.forEach((voice, index) => {
        if (voice.lang.includes('en') || voice.lang.includes('EN')) {
          const option = document.createElement('option');
          option.value = index;
          option.textContent = `${voice.name} (${voice.lang})`;
          voiceSelect.appendChild(option);
        }
      });
      
      voiceSelect.addEventListener('change', () => {
        const val = voiceSelect.value;
        if (val === 'default') {
          state.selectedVoice = null;
        } else {
          state.selectedVoice = voices[parseInt(val)];
        }
      });
    }
  };

  // Start Voice Assistant Mode
  function startListening() {
    if (state.recognition) {
      try {
        state.recognition.start();
      } catch (err) {
        console.warn('Recognition already running:', err);
      }
    } else {
      showNotification('Speech recognition not supported in this browser.', 'warning');
    }
  }

  // Stop Listening
  function stopListening() {
    if (state.recognition) {
      state.recognition.stop();
    }
  }

  // Update Voice Assistant Circle UI
  function updateVoiceWidgetUI(status) {
    // status: 'idle' | 'listening' | 'processing' | 'speaking'
    
    // Update floating circle classes
    floatingVoiceBtn.className = 'voice-circle';
    largeVoiceCircle.className = 'large-voice-circle';
    
    if (status === 'listening') {
      floatingVoiceBtn.classList.add('listening');
      largeVoiceCircle.classList.add('listening');
    } else if (status === 'processing') {
      floatingVoiceBtn.classList.add('processing');
      largeVoiceCircle.classList.add('processing');
    } else if (status === 'speaking') {
      floatingVoiceBtn.classList.add('speaking');
      largeVoiceCircle.classList.add('speaking');
    }
    
    // Toggle animations on large circle
    const visualizer = document.getElementById('voice-visualizer');
    if (status === 'speaking') {
      visualizer.style.display = 'flex';
    } else {
      visualizer.style.display = 'none';
    }
  }

  // Open and Close Voice Mode Fullscreen overlay
  function enterVoiceMode() {
    state.voiceModeActive = true;
    voiceOverlay.classList.add('active');
    updateVoiceWidgetUI('idle');
    voiceStatusText.textContent = 'Voice Mode Ready';
    voiceSubtext.textContent = 'Click the circle to talk to JARVIS';
    
    // Auto-start listening on enter
    setTimeout(startListening, 500);
  }

  function exitVoiceMode() {
    state.voiceModeActive = false;
    voiceOverlay.classList.remove('active');
    stopListening();
    window.speechSynthesis.cancel();
    state.isSpeaking = false;
    state.isListening = false;
  }

  // Event Listeners for Voice Mode
  floatingVoiceBtn.addEventListener('click', enterVoiceMode);
  closeVoiceBtn.addEventListener('click', exitVoiceMode);
  
  largeVoiceCircle.addEventListener('click', () => {
    if (state.isListening) {
      stopListening();
    } else if (state.isSpeaking) {
      window.speechSynthesis.cancel();
      state.isSpeaking = false;
      updateVoiceWidgetUI('idle');
    } else {
      startListening();
    }
  });

  textToggleVoiceBtn.addEventListener('click', () => {
    exitVoiceMode();
    chatInput.focus();
  });

  // Submit Text/Voice Message to the Agent Backend
  async function submitMessage(query) {
    if (!query || query.trim() === '') return;
    
    // Show User Message
    addMessageToChat('You', query, 'user');
    
    state.isProcessing = true;
    updateVoiceWidgetUI('processing');
    
    if (state.voiceModeActive) {
      voiceStatusText.textContent = 'Thinking...';
      voiceSubtext.textContent = `"${query}"`;
    }

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          thread_id: state.threadId
        })
      });
      
      const data = await response.json();
      
      state.isProcessing = false;
      
      if (data.thought_logs) {
        addThoughtLogs(data.thought_logs);
      }
      
      addMessageToChat('JARVIS', data.response, 'agent');

      if (state.voiceModeActive) {
        speakText(data.response);
      }
    } catch (err) {
      console.error(err);
      state.isProcessing = false;
      updateVoiceWidgetUI('idle');
      addMessageToChat('System', 'An error occurred while getting response.', 'system');
      
      if (state.voiceModeActive) {
        voiceStatusText.textContent = 'Error';
        voiceSubtext.textContent = 'Could not contact the server.';
      }
    }
  }

  // Add a Thought Log container for Agent reasoning
  function addThoughtLogs(thoughtText) {
    if (!thoughtText || thoughtText.trim() === '') return;
    
    const thoughtDiv = document.createElement('div');
    thoughtDiv.className = 'thought-toggle';
    thoughtDiv.innerHTML = `
      <div class="thought-header">💡 View Agent Thoughts & Tools Execution <span>▼</span></div>
      <div class="thought-body" style="display: none;">${escapeHtml(thoughtText)}</div>
    `;
    
    const header = thoughtDiv.querySelector('.thought-header');
    const body = thoughtDiv.querySelector('.thought-body');
    
    header.addEventListener('click', () => {
      const isHidden = body.style.display === 'none';
      body.style.display = isHidden ? 'block' : 'none';
      header.querySelector('span').textContent = isHidden ? '▲' : '▼';
    });
    
    chatContainer.appendChild(thoughtDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  // Render text messages into the UI
  function addMessageToChat(sender, text, type) {
    const msg = document.createElement('div');
    msg.className = `message ${type}`;
    
    // Parse formatting (very basic markdown-like list & newline rendering)
    const formattedText = parseMarkdown(text);

    msg.innerHTML = `
      <div class="message-label">${sender}</div>
      <div class="message-bubble">${formattedText}</div>
    `;
    
    chatContainer.appendChild(msg);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  // Escape HTML helper
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Basic markdown compiler for cleaner chat bubbles
  function parseMarkdown(text) {
    let html = escapeHtml(text);
    // Bullet points
    html = html.replace(/^\*\s(.*)/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Code blocks
    html = html.replace(/`(.*?)`/g, '<code>$1</code>');
    // New lines
    html = html.replace(/\n/g, '<br>');
    return html;
  }

  // Notification Toast Helper
  function showNotification(msg, type = 'success') {
    const toast = document.createElement('div');
    toast.style.position = 'fixed';
    toast.style.top = '24px';
    toast.style.right = '24px';
    toast.style.padding = '12px 24px';
    toast.style.borderRadius = '8px';
    toast.style.color = '#fff';
    toast.style.fontFamily = 'var(--font-main)';
    toast.style.fontWeight = '600';
    toast.style.zIndex = '999';
    toast.style.backdropFilter = 'blur(10px)';
    toast.style.boxShadow = '0 10px 30px rgba(0,0,0,0.3)';
    toast.style.animation = 'fadeIn 0.3s ease-out';
    
    if (type === 'success') {
      toast.style.background = 'rgba(16, 185, 129, 0.85)';
      toast.style.border = '1px solid rgba(16, 185, 129, 0.3)';
    } else if (type === 'error') {
      toast.style.background = 'rgba(239, 68, 68, 0.85)';
      toast.style.border = '1px solid rgba(239, 68, 68, 0.3)';
    } else {
      toast.style.background = 'rgba(245, 158, 11, 0.85)';
      toast.style.border = '1px solid rgba(245, 158, 11, 0.3)';
    }

    toast.textContent = msg;
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.5s ease';
      setTimeout(() => toast.remove(), 500);
    }, 4000);
  }

  // Send message on Enter key press
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const val = chatInput.value.trim();
      if (val) {
        submitMessage(val);
        chatInput.value = '';
      }
    }
  });

  // Send message on button click
  sendBtn.addEventListener('click', () => {
    const val = chatInput.value.trim();
    if (val) {
      submitMessage(val);
      chatInput.value = '';
    }
  });

  // Toggle TTS speaking voice directly in standard mode
  voiceBtn.addEventListener('click', () => {
    state.ttsEnabled = !state.ttsEnabled;
    voiceBtn.classList.toggle('active', state.ttsEnabled);
    if (!state.ttsEnabled) {
      window.speechSynthesis.cancel();
      state.isSpeaking = false;
      updateVoiceWidgetUI('idle');
    }
    showNotification(state.ttsEnabled ? 'Voice output enabled.' : 'Voice output muted.');
  });

  // Bootstrapping
  initSpeechRecognition();
  loadTools();
  loadConfig();
  
  // Set voice button initially active since TTS is enabled
  voiceBtn.classList.add('active');
});
