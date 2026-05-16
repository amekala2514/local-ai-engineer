// Local AI Assistant - Day 8 UI
//
// Vanilla JS app that talks to the Agent API via session cookies.
// No tokens in browser storage. If the cookie is invalid or missing,
// the API returns 401 and we redirect to /login.html.

(() => {
  // ---------- State ----------

  const state = {
    conversationId: null,
    isStreaming: false,
    abortController: null,
  };

  // ---------- DOM ----------

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

  function renderEmptyState() {
    els.chatWindow.innerHTML = `
      <div class="empty-state">
        <p>No messages yet. Type something below to start a conversation.</p>
      </div>
    `;
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
      metaDiv.textContent = meta;
      div.appendChild(metaDiv);
    }

    els.chatWindow.appendChild(div);
    scrollChatToBottom();
    return body;
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

    const messageBody = addMessage('assistant', '', null);
    let accumulated = '';
    let modelUsed = null;

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
            if (modelUsed) {
              const metaDiv = document.createElement('div');
              metaDiv.className = 'message-meta';
              metaDiv.textContent = `via ${modelUsed}`;
              messageBody.parentElement.appendChild(metaDiv);
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
            if (parsed.error) {
              messageBody.parentElement.className = 'message error';
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
        // redirect already happened
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
    state.conversationId = null;
    els.chatWindow.innerHTML = '';
    renderEmptyState();
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
    els.messageInput.focus();
  }

  init();
})();
