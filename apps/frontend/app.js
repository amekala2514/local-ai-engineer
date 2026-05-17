// Local AI Assistant - Day 13a UI
//
// Adds: rename/delete conversations, regenerate, copy code, syntax highlighting,
// smart auto-scroll, sources collapsed by default, better connection state.

(() => {
  const state = {
    conversationId: null,
    conversationCollectionId: null,
    isStreaming: false,
    abortController: null,
    conversations: [],
    collections: [],
    activeView: 'chat',
    activeCollection: null,
    autoScroll: true,  // when true, new content scrolls to bottom
    openMenu: null,    // currently-open sidebar item menu (DOM element)
  };

  const els = {
    chatView: document.getElementById('chat-view'),
    collectionView: document.getElementById('collection-view'),
    chatWindow: document.getElementById('chat-window'),
    form: document.getElementById('chat-form'),
    messageInput: document.getElementById('message-input'),
    modelPicker: document.getElementById('model-picker'),
    sendButton: document.getElementById('send-button'),
    stopButton: document.getElementById('stop-button'),
    newConversation: document.getElementById('new-conversation'),
    newCollection: document.getElementById('new-collection'),
    logoutButton: document.getElementById('logout-button'),
    statusLine: document.getElementById('status-line'),
    conversationList: document.getElementById('conversation-list'),
    collectionList: document.getElementById('collection-list'),
    conversationTitle: document.getElementById('conversation-title'),
    collectionBadge: document.getElementById('collection-badge'),
    collectionBadgeName: document.getElementById('collection-badge-name'),
    newConvDialog: document.getElementById('new-conversation-dialog'),
    newConvCollection: document.getElementById('new-conv-collection'),
    newConvCancel: document.getElementById('new-conv-cancel'),
    newConvCreate: document.getElementById('new-conv-create'),
    newCollDialog: document.getElementById('new-collection-dialog'),
    newCollName: document.getElementById('new-coll-name'),
    newCollError: document.getElementById('new-coll-error'),
    newCollCancel: document.getElementById('new-coll-cancel'),
    newCollCreate: document.getElementById('new-coll-create'),
    collViewName: document.getElementById('collection-view-name'),
    collViewInfo: document.getElementById('collection-view-info'),
    uploadArea: document.getElementById('upload-area'),
    uploadInput: document.getElementById('upload-input'),
    uploadStatus: document.getElementById('upload-status'),
    collClose: document.getElementById('collection-close'),
    collDelete: document.getElementById('collection-delete'),
  };

  // ---------- Utilities ----------

  function redirectToLogin() { window.location.href = '/login.html'; }

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

  function setView(view) {
    state.activeView = view;
    els.chatView.hidden = view !== 'chat';
    els.collectionView.hidden = view !== 'collection';
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

  // ---------- Smart auto-scroll ----------

  function isNearBottom() {
    const el = els.chatWindow;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  }

  function maybeScrollToBottom() {
    if (state.autoScroll) {
      els.chatWindow.scrollTop = els.chatWindow.scrollHeight;
    }
  }

  // When the user scrolls, decide whether auto-scroll should be re-enabled.
  function attachScrollListener() {
    els.chatWindow.addEventListener('scroll', () => {
      state.autoScroll = isNearBottom();
    });
  }

  // ---------- Code blocks: highlight + copy button ----------

  function enhanceCodeBlocks(container) {
    const blocks = container.querySelectorAll('pre code');
    blocks.forEach((block) => {
      // Skip if already enhanced
      if (block.dataset.enhanced === '1') return;
      // Highlight
      if (window.hljs) {
        try { hljs.highlightElement(block); } catch (e) {}
      }
      // Add copy button to the parent <pre>
      const pre = block.parentElement;
      if (pre && !pre.querySelector('.copy-code-btn')) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'copy-code-btn';
        btn.textContent = 'Copy';
        btn.addEventListener('click', async () => {
          try {
            await navigator.clipboard.writeText(block.textContent);
            btn.textContent = 'Copied';
            btn.classList.add('copied');
            setTimeout(() => {
              btn.textContent = 'Copy';
              btn.classList.remove('copied');
            }, 1500);
          } catch (e) {
            btn.textContent = 'Failed';
            setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
          }
        });
        pre.appendChild(btn);
      }
      block.dataset.enhanced = '1';
    });
  }

  // ---------- Sources panel (collapsed by default) ----------

  function buildSourcesPanel(sources) {
    if (!sources || sources.length === 0) return null;
    const panel = document.createElement('details');
    panel.className = 'sources-panel';
    // Closed by default — no `open` attribute

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

  // ---------- Messages ----------

  function addMessage(role, content, meta, sources, options = {}) {
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

    if (sources && sources.length) {
      const panel = buildSourcesPanel(sources);
      if (panel) div.appendChild(panel);
    }

    // Assistant messages get a Regenerate button (visible on hover)
    if (role === 'assistant' && !options.suppressActions) {
      const actions = document.createElement('div');
      actions.className = 'message-actions';
      const regen = document.createElement('button');
      regen.type = 'button';
      regen.className = 'message-action-btn';
      regen.textContent = 'Regenerate';
      regen.addEventListener('click', () => regenerateLast(div));
      actions.appendChild(regen);
      div.appendChild(actions);
    }

    enhanceCodeBlocks(body);

    els.chatWindow.appendChild(div);
    maybeScrollToBottom();
    return { messageDiv: div, body };
  }

  // ---------- Regenerate ----------

  async function regenerateLast(messageDiv) {
    if (state.isStreaming) return;
    if (!state.conversationId) return;

    // Remove the assistant message from the DOM immediately
    messageDiv.remove();
    setStatus('Regenerating…', '');
    state.isStreaming = true;
    els.sendButton.disabled = true;

    try {
      const res = await apiFetch(
        `/api/conversations/${state.conversationId}/regenerate`,
        { method: 'POST' }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        addMessage('error', `Regeneration failed: ${err.detail || res.status}`, null, null);
        return;
      }
      const data = await res.json();
      const meta = `via <strong>${escapeHtml(data.model_used)}</strong>`;
      addMessage('assistant', data.reply, meta, data.sources || null);
      setStatus('Ready', 'ok');
    } catch (e) {
      if (e.message !== 'Not authenticated') {
        addMessage('error', `Network error: ${e.message}`, null, null);
        setStatus('Error', 'error');
      }
    } finally {
      state.isStreaming = false;
      els.sendButton.disabled = false;
      els.messageInput.focus();
    }
  }

  // ---------- Sidebar item menus ----------

  function closeOpenMenu() {
    if (state.openMenu) {
      state.openMenu.hidden = true;
      state.openMenu = null;
    }
  }

  function buildItemMenu(actions) {
    const menu = document.createElement('div');
    menu.className = 'item-menu';
    menu.hidden = true;
    for (const a of actions) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'item-menu-action';
      if (a.destructive) btn.classList.add('destructive');
      btn.textContent = a.label;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeOpenMenu();
        a.onClick();
      });
      menu.appendChild(btn);
    }
    return menu;
  }

  function attachMenuButton(itemEl, actions) {
    const menu = buildItemMenu(actions);
    itemEl.appendChild(menu);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'item-menu-btn';
    btn.title = 'More';
    btn.textContent = '⋯';
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const wasOpen = !menu.hidden;
      closeOpenMenu();
      if (!wasOpen) {
        menu.hidden = false;
        state.openMenu = menu;
      }
    });
    itemEl.appendChild(btn);
  }

  // ---------- Collections ----------

  async function loadCollections() {
    try {
      const res = await apiFetch('/api/collections');
      if (!res.ok) {
        els.collectionList.innerHTML = '<p class="empty-list">Failed to load.</p>';
        return;
      }
      state.collections = await res.json();
      renderCollections();
      renderCollectionOptions();
    } catch (e) {
      if (e.message !== 'Not authenticated') console.warn(e);
    }
  }

  function renderCollections() {
    if (state.collections.length === 0) {
      els.collectionList.innerHTML = '<p class="empty-list">No collections yet.</p>';
      return;
    }
    els.collectionList.innerHTML = '';
    for (const col of state.collections) {
      const item = document.createElement('div');
      item.className = 'collection-item';
      if (col.name === state.activeCollection) item.classList.add('active');
      item.dataset.name = col.name;

      const nameEl = document.createElement('span');
      nameEl.className = 'collection-item-name';
      nameEl.textContent = col.name;
      item.appendChild(nameEl);

      const countEl = document.createElement('span');
      countEl.className = 'collection-item-count';
      countEl.textContent = `${col.points_count}`;
      item.appendChild(countEl);

      item.addEventListener('click', () => openCollectionView(col.name));
      els.collectionList.appendChild(item);
    }
  }

  function renderCollectionOptions() {
    const select = els.newConvCollection;
    select.innerHTML = '<option value="">None — plain chat</option>';
    for (const col of state.collections) {
      const opt = document.createElement('option');
      opt.value = col.name;
      opt.textContent = `${col.name}  (${col.points_count} chunks)`;
      select.appendChild(opt);
    }
  }

  function highlightActiveCollection() {
    const items = els.collectionList.querySelectorAll('.collection-item');
    items.forEach(item => {
      item.classList.toggle('active', item.dataset.name === state.activeCollection);
    });
  }

  function openCollectionView(name) {
    if (state.isStreaming) return;
    state.activeCollection = name;
    highlightActiveCollection();

    els.collViewName.textContent = name;
    const col = state.collections.find(c => c.name === name);
    els.collViewInfo.textContent = col ? `${col.points_count} chunks indexed` : '';
    els.uploadStatus.hidden = true;
    setView('collection');
  }

  function closeCollectionView() {
    state.activeCollection = null;
    highlightActiveCollection();
    setView('chat');
  }

  async function uploadFile(file) {
    if (!file) return;
    const name = state.activeCollection;
    if (!name) return;
    if (!/\.(pdf|md)$/i.test(file.name)) {
      showUploadStatus('Unsupported file type. Use .pdf or .md.', 'error');
      return;
    }
    showUploadStatus(`Uploading ${file.name}…`, 'uploading');
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await apiFetch(`/api/collections/${encodeURIComponent(name)}/files`, {
        method: 'POST', body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showUploadStatus(`Upload failed: ${err.detail || res.status}`, 'error');
        return;
      }
      const result = await res.json();
      showUploadStatus(`Ingested ${result.filename}: ${result.chunks_stored} chunks`, 'success');
      await loadCollections();
      const col = state.collections.find(c => c.name === name);
      if (col) els.collViewInfo.textContent = `${col.points_count} chunks indexed`;
    } catch (e) {
      if (e.message !== 'Not authenticated') {
        showUploadStatus(`Network error: ${e.message}`, 'error');
      }
    }
  }

  function showUploadStatus(message, kind) {
    els.uploadStatus.hidden = false;
    els.uploadStatus.textContent = message;
    els.uploadStatus.className = kind;
  }

  async function deleteActiveCollection() {
    const name = state.activeCollection;
    if (!name) return;
    if (!confirm(`Delete collection "${name}"? This removes all indexed chunks. Files on disk are kept.`)) return;
    try {
      const res = await apiFetch(`/api/collections/${encodeURIComponent(name)}`, { method: 'DELETE' });
      if (res.status !== 204) {
        const err = await res.json().catch(() => ({}));
        alert(`Failed to delete: ${err.detail || res.status}`);
        return;
      }
      await loadCollections();
      closeCollectionView();
    } catch (e) {
      if (e.message !== 'Not authenticated') alert(`Network error: ${e.message}`);
    }
  }

  // ---------- New collection ----------

  function openNewCollectionDialog() {
    els.newCollName.value = '';
    els.newCollError.hidden = true;
    els.newCollDialog.showModal();
    els.newCollName.focus();
  }

  async function createCollection() {
    const name = els.newCollName.value.trim();
    if (!name) {
      els.newCollError.textContent = 'Name is required.';
      els.newCollError.hidden = false;
      return;
    }
    try {
      const res = await apiFetch('/api/collections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        els.newCollError.textContent = err.detail || `Failed (HTTP ${res.status})`;
        els.newCollError.hidden = false;
        return;
      }
      els.newCollDialog.close();
      await loadCollections();
      openCollectionView(name);
    } catch (e) {
      if (e.message !== 'Not authenticated') {
        els.newCollError.textContent = `Network error: ${e.message}`;
        els.newCollError.hidden = false;
      }
    }
  }

  // ---------- Conversations: list + rename + delete ----------

  async function loadConversationList() {
    try {
      const res = await apiFetch('/api/conversations?limit=200');
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
      if (conv.id === state.conversationId && state.activeView === 'chat') {
        item.classList.add('active');
      }
      item.dataset.conversationId = conv.id;
      item.dataset.collectionId = conv.collection_id || '';

      const title = document.createElement('span');
      title.className = 'conversation-item-title';
      title.textContent = conv.title || '(untitled)';
      title.title = conv.title || '';  // tooltip with full title
      if (conv.collection_id) {
        const marker = document.createElement('span');
        marker.className = 'collection-marker';
        marker.textContent = ' 📎';
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

      attachMenuButton(item, [
        { label: 'Rename', onClick: () => promptRenameConversation(conv) },
        { label: 'Delete', destructive: true, onClick: () => deleteConversation(conv) },
      ]);

      els.conversationList.appendChild(item);
    }
  }

  async function promptRenameConversation(conv) {
    const newTitle = prompt('Rename conversation:', conv.title || '');
    if (newTitle === null) return;
    const trimmed = newTitle.trim();
    if (!trimmed || trimmed === conv.title) return;
    try {
      const res = await apiFetch(`/api/conversations/${conv.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: trimmed }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(`Rename failed: ${err.detail || res.status}`);
        return;
      }
      await loadConversationList();
      if (state.conversationId === conv.id) {
        setConversationTitle(trimmed);
      }
    } catch (e) {
      if (e.message !== 'Not authenticated') alert(`Network error: ${e.message}`);
    }
  }

  async function deleteConversation(conv) {
    if (!confirm(`Delete conversation "${conv.title || '(untitled)'}"? This cannot be undone.`)) return;
    try {
      const res = await apiFetch(`/api/conversations/${conv.id}`, { method: 'DELETE' });
      if (res.status !== 204) {
        const err = await res.json().catch(() => ({}));
        alert(`Delete failed: ${err.detail || res.status}`);
        return;
      }
      if (state.conversationId === conv.id) {
        state.conversationId = null;
        state.conversationCollectionId = null;
        els.chatWindow.innerHTML = '';
        setConversationTitle('New conversation');
        setCollectionBadge(null);
        renderEmptyState();
      }
      await loadConversationList();
    } catch (e) {
      if (e.message !== 'Not authenticated') alert(`Network error: ${e.message}`);
    }
  }

  function highlightActiveConversation() {
    const items = els.conversationList.querySelectorAll('.conversation-item');
    items.forEach(item => {
      item.classList.toggle('active', item.dataset.conversationId === state.conversationId);
    });
  }

  async function loadConversation(conversationId, title, collectionId) {
    if (state.isStreaming) return;
    try {
      const res = await apiFetch(`/api/conversations/${conversationId}/messages`);
      if (!res.ok) {
        addMessage('error', `Failed to load conversation: HTTP ${res.status}`, null, null);
        return;
      }
      const messages = await res.json();
      state.conversationId = conversationId;
      state.conversationCollectionId = collectionId || null;
      state.autoScroll = true;
      els.chatWindow.innerHTML = '';
      setConversationTitle(title);
      setCollectionBadge(collectionId);

      if (messages.length === 0) {
        renderEmptyState();
      } else {
        for (const msg of messages) {
          const meta = msg.model ? `via ${escapeHtml(msg.model)}` : null;
          // History messages don't get a Regenerate button — only the live last one
          const isLast = msg === messages[messages.length - 1];
          addMessage(msg.role, msg.content, meta, null, { suppressActions: !isLast || msg.role !== 'assistant' });
        }
      }
      setView('chat');
      highlightActiveConversation();
    } catch (e) {
      if (e.message !== 'Not authenticated') console.error(e);
    }
  }

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
      state.autoScroll = true;
      els.chatWindow.innerHTML = '';
      setConversationTitle(conv.title || 'New conversation');
      setCollectionBadge(conv.collection_id);
      renderEmptyState();
      setView('chat');
      await loadConversationList();
      els.messageInput.focus();
    } catch (e) {
      if (e.message !== 'Not authenticated') alert(`Network error: ${e.message}`);
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

    const { messageDiv, body: messageBody } = addMessage('assistant', '', null, null, { suppressActions: true });
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
              messageDiv.appendChild(metaDiv);
            }
            if (sources && sources.length) {
              const panel = buildSourcesPanel(sources);
              if (panel) messageDiv.appendChild(panel);
            }
            // Add the Regenerate button now that streaming is complete
            const actions = document.createElement('div');
            actions.className = 'message-actions';
            const regen = document.createElement('button');
            regen.type = 'button';
            regen.className = 'message-action-btn';
            regen.textContent = 'Regenerate';
            regen.addEventListener('click', () => regenerateLast(messageDiv));
            actions.appendChild(regen);
            messageDiv.appendChild(actions);

            enhanceCodeBlocks(messageBody);

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
              maybeScrollToBottom();
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

    addMessage('user', message, null, null, { suppressActions: true });
    els.messageInput.value = '';
    state.autoScroll = true;

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
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
    } catch (e) {}
    redirectToLogin();
  }

  function handleKeyDown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      els.form.requestSubmit();
    }
  }

  function wireUploadArea() {
    els.uploadArea.addEventListener('click', () => els.uploadInput.click());
    els.uploadInput.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) uploadFile(file);
      els.uploadInput.value = '';
    });
    els.uploadArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      els.uploadArea.classList.add('drag-active');
    });
    els.uploadArea.addEventListener('dragleave', () => {
      els.uploadArea.classList.remove('drag-active');
    });
    els.uploadArea.addEventListener('drop', (e) => {
      e.preventDefault();
      els.uploadArea.classList.remove('drag-active');
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) uploadFile(file);
    });
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
      if (data.ollama_reachable) setStatus(`Connected (v${data.version})`, 'ok');
      else setStatus('Ollama unreachable — check Ollama is running', 'error');
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
    els.newCollection.addEventListener('click', openNewCollectionDialog);
    els.newConvCancel.addEventListener('click', () => els.newConvDialog.close());
    els.newConvCreate.addEventListener('click', createNewConversation);
    els.newCollCancel.addEventListener('click', () => els.newCollDialog.close());
    els.newCollCreate.addEventListener('click', createCollection);
    els.collClose.addEventListener('click', closeCollectionView);
    els.collDelete.addEventListener('click', deleteActiveCollection);
    els.logoutButton.addEventListener('click', handleLogout);
    els.messageInput.addEventListener('keydown', handleKeyDown);

    // Click anywhere else to close an open menu
    document.addEventListener('click', () => closeOpenMenu());

    wireUploadArea();
    attachScrollListener();

    renderEmptyState();
    await checkHealth();
    await loadCollections();
    await loadConversationList();
    els.messageInput.focus();
  }

  init();
})();
