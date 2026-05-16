// Local AI Assistant - Day 9 UI
//
// Adds: conversation sidebar, auto-routing display, click-to-load history.

(() => {
  // ---------- State ----------

  const state = {
    conversationId: null,
    isStreaming: false,
    abortController: null,
    conversations: [],
  };

  // ---------- DOM ----------

  const els = {
    app: document.querySelector('.app'),
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
    if (window.marked) {
      return marked.parse(text);
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
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
    if (sameDay) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }

  function addMessage(role, content, meta) {
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

    els.chatWindow.appendChild(div);
    scrollChatToBottom();
    return { messageDiv: div, body };
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
      if (e.message === 'Not authenticated') return;
      els.conversationList.innerHTML = '<p class="empty-list">Network error.</p>';
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
      if (conv.id === state.conversationId) {
        item.classList.add('active');
      }
      item.dataset.conversationId = conv.id;

      const title = document.createElement('span');
      title.className = 'conversation-item-title';
      title.textContent = conv.title || '(untitled)';
      item.appendChild(title);

      const date = document.createElement('span');
      date.className = 'conversation-item-date';
      date.textContent = formatDate(conv.updated_at);
      item.appendChild(date);

      item.addEventListener('click', () => {
        loadConversation(conv.id, conv.title);
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

  // ---------- Load and rehydrate a conversation ----------

  async function loadConversation(conversationId, title) {
    if (state.isStreaming) return;  // Don't switch mid-stream

    try {
      const res = await apiFetch(`/api/conversations/${conversationId}/messages`);
      if (!res.ok) {
        addMessage('error', `Failed to load conversation: HTTP ${res.status}`);
        return;
      }
      const messages = await res.json();

      state.conversationId = conversationId;
      els.chatWindow.innerHTML = '';
      setConversationTitle(title);

      if (messages.length === 0) {
        renderEmptyState();
      } else {
        for (const msg of messages) {
          const meta = msg.model ? `via ${msg.model}` : null;
          addMessage(msg.role, msg.content, meta);
        }
      }

      highlightActiveConversation();
    } catch (e) {
      if (e.message === 'Not authenticated') return;
      console.error(e);
    }
  }

  // ---------- Streaming chat call ----------

  async function streamChat(message, taskType) {
    state.abortController = new AbortController();

    const response = await apiFetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        task_type: taskType,
        conversation_id: state.conversationId,
      }),
      signal: state.abortController.signal,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const { messageDiv, body: messageBody } = addMessage('assistant', '', null);
    let accumulated = '';
    let modelUsed = null;
    let routingReason = null;
    let routingTaskType = null;
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
            // Decorate the message with model and routing info
            if (modelUsed) {
              const metaDiv = document.createElement('div');
              metaDiv.className = 'message-meta';
              let html = `via <strong>${escapeHtml(modelUsed)}</strong>`;
              if (routingReason && taskType === 'auto') {
                html += ` <span class="routing-reason">(${escapeHtml(routingReason)})</span>`;
              }
              metaDiv.innerHTML = html;
              messageDiv.appendChild(metaDiv);
            }
            // If this was a new conversation, refresh the sidebar
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
            if (parsed.model && !modelUsed) {
              modelUsed = parsed.model;
            }
            if (parsed.routing_reason && !routingReason) {
              routingReason = parsed.routing_reason;
              routingTaskType = parsed.task_type;
            }
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

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ---------- Form handlers ----------

  async function handleSubmit(event) {
    event.preventDefault();
    if (state.isStreaming) return;

    const message = els.messageInput.value.trim();
    if (!message) return;

    const taskType = els.modelPicker.value;

    addMessage('user', message, null);
    els.messageInput.value = '';

    state.isStreaming = true;
    els.sendButton.disabled = true;
    els.stopButton.disabled = false;
    setStatus('Generating…', '');

    try {
      await streamChat(message, taskType);
      setStatus('Ready', 'ok');
    } catch (e) {
      if (e.name === 'AbortError') {
        setStatus('Stopped', '');
      } else if (e.message === 'Not authenticated') {
        return;
      } else {
        console.error(e);
        addMessage('error', `**Error:** ${e.message}`, null);
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

  function handleNewConversation() {
    if (state.isStreaming) return;
    state.conversationId = null;
    els.chatWindow.innerHTML = '';
    setConversationTitle('New conversation');
    renderEmptyState();
    highlightActiveConversation();
    els.messageInput.focus();
    setStatus('Ready', 'ok');
  }

  async function handleLogout() {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
      });
    } catch (e) {
      console.warn('Logout request failed:', e);
    }
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
      if (res.status === 401) {
        redirectToLogin();
        return false;
      }
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
      if (data.ollama_reachable) {
        setStatus(`Connected (${data.version})`, 'ok');
      } else {
        setStatus('Ollama unreachable', 'error');
      }
    } catch (e) {
      setStatus('Cannot reach Agent API', 'error');
    }
  }

  async function init() {
    const ok = await checkAuth();
    if (!ok) return;

    els.form.addEventListener('submit', handleSubmit);
    els.stopButton.addEventListener('click', handleStop);
    els.newConversation.addEventListener('click', handleNewConversation);
    els.logoutButton.addEventListener('click', handleLogout);
    els.messageInput.addEventListener('keydown', handleKeyDown);

    renderEmptyState();
    await checkHealth();
    await loadConversationList();
    els.messageInput.focus();
  }

  init();
})();
