// Local AI Assistant - Day 11 UI
//
// Adds: collection picker on new conversation, sources panel under replies.

(() => {
  const state = {
    conversationId: null,
    conversationCollectionId: null,
    isStreaming: false,
    abortController: null,
    conversations: [],
    collections: [],
  };

  const els = {
    chatWindow: document.getElementById('chat-window'),
    form: document.getElementById('chat-form'),
    messageInput: document.getElementById('message-input'),
    modelPicker: document.getElementById('model-picker'),
    sendButton: document.getElementById('send-button'),
    stopButton: document.getElementById('stop-button'),
    newConversation: document.getElementById('new-conversation'),
    logoutButton: document.getElementById('logout-button'),
    statusLine: document.getElementById('status-line'),
    conversationList: document.getElementById('conversation-list'),
    conversationTitle: document.getElementById('conversation-title'),
    collectionBadge: document.getElementById('collection-badge'),
    collectionBadgeName: document.getElementById('collection-badge-name'),
    newConvDialog: document.getElementById('new-conversation-dialog'),
    newConvCollection: document.getElementById('new-conv-collection'),
    newConvCancel: document.getElementById('new-conv-cancel'),
    newConvCreate: document.getElementById('new-conv-create'),
  };

  // ---------- Utilities ----------

  function redirectToLogin() {
    window.location.href = '/login.html';
  }

  async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      ...options,
    });
    if (response.status === 401) {
      redirectToLogin();
      throw new Error('Not authenticated');
    }
    return response;
  }

  function renderMarkdown(text) {
    if (window.marked) return marked.parse(text);
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function scrollChatToBottom() {
    els.chatWindow.scrollTop = els.chatWindow.scrollHeight;
  }

  function setStatus(text, kind) {
    els.statusLine.textContent = text;
    els.statusLine.className = kind || '';
  }

  function setConversationTitle(title) {
    els.conversationTitle.textContent = title || 'New conversation';
  }

  function setCollectionBadge(collectionId) {
    if (collectionId) {
      els.collectionBadge.hidden = false;
      els.collectionBadgeName.textContent = collectionId;
    } else {
      els.collectionBadge.hidden = true;
    }
  }

  function renderEmptyState() {
    els.chatWindow.innerHTML = `
      <div class="empty-state">
        <p>No messages yet. Type something below to start a conversation.</p>
      </div>
    `;
  }

  function formatDate(iso) {
    const d = new Date(iso);
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }

  function buildSourcesPanel(sources) {
    if (!sources || sources.length === 0) return null;
    const panel = document.createElement('details');
    panel.className = 'sources-panel';

    const summary = document.createElement('summary');
    summary.textContent = `Sources (${sources.length})`;
    panel.appendChild(summary);

    sources.forEach((src, i) => {
      const item = document.createElement('div');
      item.className = 'source-item';

      const header = document.createElement('div');
      header.className = 'source-item-header';
      header.textContent = `[${i + 1}] ${src.source_file}`;

      const score = document.createElement('span');
      score.className = 'source-item-score';
      score.textContent = `score ${src.score.toFixed(3)}`;
      header.appendChild(score);

      if (src.section_path && src.section_path.length) {
        const loc = document.createElement('span');
        loc.className = 'source-item-location';
        loc.textContent = src.section_path.join(' > ');
        header.appendChild(loc);
      } else if (src.page_number) {
        const loc = document.createElement('span');
        loc.className = 'source-item-location';
        loc.textContent = `page ${src.page_number}`;
        header.appendChild(loc);
      }

      item.appendChild(header);

      const text = document.createElement('div');
      text.className = 'source-item-text';
      text.textContent = src.text;
      item.appendChild(text);

      panel.appendChild(item);
    });

    return panel;
  }

  function addMessage(role, content, meta, sources) {
    const emptyState = els.chatWindow.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const div = document.createElement('div');
    div.className = `message ${role}`;

    const body = document.createElement('div');
    body.className = 'message-body';
    body.innerHTML = renderMarkdown(content);
    div.appendChild(body);

    if (meta) {
      const metaDiv = document.createElement('div');
      metaDiv.className = 'message-meta';
      metaDiv.innerHTML = meta;
      div.appendChild(metaDiv);
    }

    if (sources) {
      const panel = buildSourcesPanel(sources);
      if (panel) div.appendChild(panel);
    }

    els.chatWindow.appendChild(div);
    scrollChatToBottom();
    return { messageDiv: div, body };
  }

  // ---------- Collections ----------

  async function loadCollections() {
    try {
      const res = await apiFetch('/api/collections');
      if (!res.ok) return;
      state.collections = await res.json();
      renderCollectionOptions();
    } catch (e) {
      if (e.message !== 'Not authenticated') console.warn(e);
    }
  }

  function renderCollectionOptions() {
    const select = els.newConvCollection;
    // Keep the "None" default option, rebuild the rest
    select.innerHTML = '<option value="">None — plain chat</option>';
    for (const col of state.collections) {
      const opt = document.createElement('option');
      opt.value = col.name;
      opt.textContent = `${col.name}  (${col.points_count} chunks)`;
      select.appendChild(opt);
    }
  }

  // ---------- Sidebar ----------

  async function loadConversationList() {
    try {
      const res = await apiFetch('/api/conversations?limit=100');
      if (!res.ok) {
        els.conversationList.innerHTML = '<p class="empty-list">Failed to load.</p>';
        return;
      }
      state.conversations = await res.json();
      renderConversationList();
    } catch (e) {
      if (e.message !== 'Not authenticated') {
        els.conversationList.innerHTML = '<p class="empty-list">Network error.</p>';
      }
    }
  }

  function renderConversationList() {
    if (state.conversations.length === 0) {
      els.conversationList.innerHTML = '<p class="empty-list">No conversations yet.</p>';
      return;
    }
    els.conversationList.innerHTML = '';
    for (const conv of state.conversations) {
      const item = document.createElement('div');
      item.className = 'conversation-item';
      if (conv.id === state.conversationId) item.classList.add('active');
      item.dataset.conversationId = conv.id;
      item.dataset.collectionId = conv.collection_id || '';

      const title = document.createElement('span');
      title.className = 'conversation-item-title';
      title.textContent = conv.title || '(untitled)';
      if (conv.collection_id) {
        const marker = document.createElement('span');
        marker.className = 'collection-marker';
        marker.textContent = '📎';
        title.appendChild(marker);
      }
      item.appendChild(title);

      const date = document.createElement('span');
      date.className = 'conversation-item-date';
      date.textContent = formatDate(conv.updated_at);
      item.appendChild(date);

      item.addEventListener('click', () => {
        loadConversation(conv.id, conv.title, conv.collection_id);
      });

      els.conversationList.appendChild(item);
    }
  }

  function highlightActiveConversation() {
    const items = els.conversationList.querySelectorAll('.conversation-item');
    items.forEach(item => {
      item.classList.toggle('active', item.dataset.conversationId === state.conversationId);
    });
  }

  // ---------- Load and rehydrate ----------

  async function loadConversation(conversationId, title, collectionId) {
    if (state.isStreaming) return;
    try {
      const res = await apiFetch(`/api/conversations/${conversationId}/messages`);
      if (!res.ok) {
        addMessage('error', `Failed to load conversation: HTTP ${res.status}`);
        return;
      }
      const messages = await res.json();
      state.conversationId = conversationId;
      state.conversationCollectionId = collectionId || null;
      els.chatWindow.innerHTML = '';
      setConversationTitle(title);
      setCollectionBadge(collectionId);

      if (messages.length === 0) {
        renderEmptyState();
      } else {
        for (const msg of messages) {
          const meta = msg.model ? `via ${escapeHtml(msg.model)}` : null;
          addMessage(msg.role, msg.content, meta, null);
        }
      }
      highlightActiveConversation();
    } catch (e) {
      if (e.message !== 'Not authenticated') console.error(e);
    }
  }

  // ---------- New conversation ----------

  function openNewConversationDialog() {
    if (state.isStreaming) return;
    els.newConvCollection.value = '';
    els.newConvDialog.showModal();
  }

  async function createNewConversation() {
    const collectionId = els.newConvCollection.value || null;
    try {
      const res = await apiFetch('/api/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collection_id: collectionId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(`Failed to create: ${err.detail || res.status}`);
        return;
      }
      const conv = await res.json();
      els.newConvDialog.close();
      state.conversationId = conv.id;
      state.conversationCollectionId = conv.collection_id;
      els.chatWindow.innerHTML = '';
      setConversationTitle(conv.title || 'New conversation');
      setCollectionBadge(conv.collection_id);
      renderEmptyState();
      await loadConversationList();
      els.messageInput.focus();
    } catch (e) {
      if (e.message !== 'Not authenticated') {
        alert(`Network error: ${e.message}`);
      }
    }
  }

  // ---------- Streaming chat ----------

  async function streamChat(message, taskType) {
    state.abortController = new AbortController();

    const body = {
      message,
      task_type: taskType,
      conversation_id: state.conversationId,
    };

    const response = await apiFetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: state.abortController.signal,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const { messageDiv, body: messageBody } = addMessage('assistant', '', null, null);
    let accumulated = '';
    let modelUsed = null;
    let routingReason = null;
    let sources = null;
    let isNewConversation = state.conversationId === null;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const event of events) {
        for (const line of event.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();

          if (data === '[DONE]') {
            const metaParts = [];
            if (modelUsed) metaParts.push(`via <strong>${escapeHtml(modelUsed)}</strong>`);
            if (routingReason && taskType === 'auto') {
              metaParts.push(`<span class="routing-reason">(${escapeHtml(routingReason)})</span>`);
            }
            if (metaParts.length) {
              const metaDiv = document.createElement('div');
              metaDiv.className = 'message-meta';
              metaDiv.innerHTML = metaParts.join(' ');
              // Insert before any existing sources panel
              const existingPanel = messageDiv.querySelector('.sources-panel');
              if (existingPanel) {
                messageDiv.insertBefore(metaDiv, existingPanel);
              } else {
                messageDiv.appendChild(metaDiv);
              }
            }
            if (sources && sources.length) {
              const panel = buildSourcesPanel(sources);
              if (panel) messageDiv.appendChild(panel);
            }
            if (isNewConversation && state.conversationId) {
              await loadConversationList();
            }
            return;
          }

          try {
            const parsed = JSON.parse(data);
            if (parsed.conversation_id && !state.conversationId) {
              state.conversationId = parsed.conversation_id;
            }
            if (parsed.model && !modelUsed) modelUsed = parsed.model;
            if (parsed.routing_reason && !routingReason) routingReason = parsed.routing_reason;
            if (parsed.sources) sources = parsed.sources;
            if (parsed.error) {
              messageDiv.className = 'message error';
              messageBody.textContent = `Error: ${parsed.error}`;
              return;
            }
            if (parsed.content) {
              accumulated += parsed.content;
              messageBody.innerHTML = renderMarkdown(accumulated);
              scrollChatToBottom();
            }
          } catch (e) {
            console.warn('Failed to parse SSE event:', data, e);
          }
        }
      }
    }
  }

  // ---------- Form handlers ----------

  async function handleSubmit(event) {
    event.preventDefault();
    if (state.isStreaming) return;
    const message = els.messageInput.value.trim();
    if (!message) return;
    const taskType = els.modelPicker.value;

    addMessage('user', message, null, null);
    els.messageInput.value = '';

    state.isStreaming = true;
    els.sendButton.disabled = true;
    els.stopButton.disabled = false;
    setStatus('Generating…', '');

    try {
      await streamChat(message, taskType);
      setStatus('Ready', 'ok');
    } catch (e) {
      if (e.name === 'AbortError') setStatus('Stopped', '');
      else if (e.message === 'Not authenticated') return;
      else {
        console.error(e);
        addMessage('error', `**Error:** ${e.message}`, null, null);
        setStatus('Error - see message above', 'error');
      }
    } finally {
      state.isStreaming = false;
      state.abortController = null;
      els.sendButton.disabled = false;
      els.stopButton.disabled = true;
      els.messageInput.focus();
    }
  }

  function handleStop() {
    if (state.abortController) state.abortController.abort();
  }

  async function handleLogout() {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST', credentials: 'same-origin',
      });
    } catch (e) {}
    redirectToLogin();
  }

  function handleKeyDown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      els.form.requestSubmit();
    }
  }

  // ---------- Startup ----------

  async function checkAuth() {
    try {
      const res = await fetch('/api/auth/me', { credentials: 'same-origin' });
      if (res.status === 401) { redirectToLogin(); return false; }
      return true;
    } catch (e) {
      setStatus('Cannot reach Agent API', 'error');
      return false;
    }
  }

  async function checkHealth() {
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      if (data.ollama_reachable) setStatus(`Connected (${data.version})`, 'ok');
      else setStatus('Ollama unreachable', 'error');
    } catch (e) {
      setStatus('Cannot reach Agent API', 'error');
    }
  }

  async function init() {
    const ok = await checkAuth();
    if (!ok) return;

    els.form.addEventListener('submit', handleSubmit);
    els.stopButton.addEventListener('click', handleStop);
    els.newConversation.addEventListener('click', openNewConversationDialog);
    els.newConvCancel.addEventListener('click', () => els.newConvDialog.close());
    els.newConvCreate.addEventListener('click', createNewConversation);
    els.logoutButton.addEventListener('click', handleLogout);
    els.messageInput.addEventListener('keydown', handleKeyDown);

    renderEmptyState();
    await checkHealth();
    await loadCollections();
    await loadConversationList();
    els.messageInput.focus();
  }

  init();
})();
