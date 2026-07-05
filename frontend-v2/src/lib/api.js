const API_BASE = '/api';

class ApiError extends Error {
  constructor(message, code, level = 'business') {
    super(message);
    this.name = 'ApiError';
    this.code = code || 0;
    this.level = level;
  }
}

function handleUnauthorized() {
  localStorage.removeItem('token');
  import('../stores/authStore').then(m => {
    // 直接重置状态，不调 logout()，避免再次发请求触发 401 死循环
    m.useAuthStore.getState().resetAuth();
  }).catch(err => {
    console.warn('[api] handleUnauthorized: failed to import authStore', err);
  });
}

async function request(path, options = {}) {
  const url = API_BASE + path;
  const headers = { Accept: 'application/json', ...(options.headers || {}) };

  const token = localStorage.getItem('token');
  if (token) headers['Authorization'] = 'Bearer ' + token;

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  let res;
  try {
    res = await fetch(url, { ...options, headers });
  } catch (err) {
    throw new ApiError('网络好像不太顺畅', 0, 'network');
  }

  if (!res.ok) {
    let message = '';
    try {
      const j = await res.json();
      message = j.message || '';
    } catch (_) {}
    if (res.status === 401) {
      handleUnauthorized();
      throw new ApiError(message || '登录已失效', 401, 'client');
    }
    throw new ApiError(message || `请求失败 (${res.status})`, res.status, 'server');
  }

  const json = await res.json();
  if (options.raw) return json;
  if (json.code !== 0) {
    throw new ApiError(json.message || '出了点小状况', json.code, 'business');
  }
  return json.data || {};
}

// ===== Auth =====
export async function login(nickname, password) {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ nickname, password }),
  });
}

export async function register(nickname, password, phone) {
  const body = { nickname, password };
  if (phone) body.phone = phone;
  return request('/auth/register', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function logout() {
  return request('/auth/logout', { method: 'POST' });
}

export async function getProfile() {
  return request('/auth/me');
}

export async function updateProfile(data) {
  return request('/auth/profile', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function changePassword(oldPassword, newPassword) {
  return request('/auth/password', {
    method: 'PUT',
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
}

export async function uploadAvatar(file) {
  const fd = new FormData();
  fd.append('file', file);
  return request('/auth/avatar', { method: 'POST', body: fd });
}

// ===== Photo Recognition =====
const POLL_INTERVAL = 1500;
const POLL_MAX = 40;          // 最多轮询 40 次 ≈ 60s
const POLL_TIMEOUT = 60000;   // 60s 硬超时（独立于 POLL_MAX，防止后端响应慢拖死）

function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new ApiError('已取消', 0, 'client'));
      return;
    }
    const t = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(t);
      reject(new ApiError('已取消', 0, 'client'));
    }, { once: true });
  });
}

export async function submitRecognize(file) {
  const fd = new FormData();
  fd.append('file', file);
  return request('/recognize-dish', { method: 'POST', body: fd });
}

export async function pollRecognize(taskId) {
  return request('/recognize/result/' + encodeURIComponent(taskId));
}

export async function recognizeWithPolling(file, opts = {}) {
  const { onProgress, signal } = opts;
  const { task_id } = await submitRecognize(file);
  if (!task_id) throw new ApiError('未拿到任务 ID', 0, 'business');

  const startedAt = Date.now();
  for (let i = 0; i < POLL_MAX; i++) {
    if (signal?.aborted) throw new ApiError('已取消', 0, 'client');
    if (Date.now() - startedAt > POLL_TIMEOUT) {
      throw new ApiError('识别超时，请稍后重试', 0, 'timeout');
    }
    await sleep(POLL_INTERVAL, signal); // 可被 abort 中断
    const r = await pollRecognize(task_id);
    onProgress?.(Math.min(95, (i + 1) * 2.5));
    if (r.status === 'done') return r;  // 返回完整 result（含 ingredients + dish + pairing）
    if (r.status === 'failed') throw new ApiError(r.error || '识别失败', 0, 'business');
  }
  throw new ApiError('识别超时', 0, 'timeout');
}

// ===== AI Chat (SSE) =====
const SSE_DONE = '[DONE]';

export function streamChat(body, handlers) {
  const token = localStorage.getItem('token');
  const controller = new AbortController();

  fetch(`${API_BASE}/chat?stream=true`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? 'Bearer ' + token : '',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).then(async (res) => {
    if (!res.ok) {
      const text = await res.text();
      handlers.onError?.(new ApiError(text || '对话失败', res.status));
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const part of parts) {
        if (!part.trim()) continue;
        let eventName = 'message';
        const dataLines = [];
        for (const line of part.split('\n')) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim();
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
        }
        const dataStr = dataLines.join('');
        if (!dataStr) continue;

        if (eventName === 'done' || dataStr === SSE_DONE) {
          handlers.onDone?.();
          return;
        }
        if (eventName === 'heartbeat') continue;

        let payload;
        try { payload = JSON.parse(dataStr); } catch (_) { continue; }

        if (eventName === 'delta' && typeof payload.delta === 'string') {
          handlers.onDelta?.(payload.delta);
        }
      }
    }
    handlers.onDone?.();
  }).catch(err => {
    if (err.name !== 'AbortError') {
      handlers.onError?.(err);
    }
  });

  return controller;
}

// ===== Preferences =====
export async function getPreferences() {
  return request('/preferences');
}

export async function updatePreferences(data) {
  return request('/preferences', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// ===== User Center（Phase 3 个人中心）=====
export async function getUserProfile() {
  return request('/user/profile');
}

export async function updateUserProfile(data) {
  return request('/user/profile', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function updateUserBody(data) {
  return request('/user/body', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function updateUserTarget(data) {
  return request('/user/target', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function listCollectFoods() {
  return request('/user/collect');
}

export async function toggleCollectFood(foodId) {
  return request('/user/collect/' + encodeURIComponent(foodId), {
    method: 'POST',
  });
}

// ===== Camera 拍照识菜（阶段 6）=====
export async function uploadCameraImage(file) {
  const formData = new FormData();
  formData.append('file', file);
  const token = localStorage.getItem('token');
  const res = await fetch(API_BASE + '/camera/upload', {
    method: 'POST',
    headers: token ? { Authorization: 'Bearer ' + token } : {},
    body: formData,
  });
  if (!res.ok) {
    const err = new Error('HTTP ' + res.status);
    err.status = res.status;
    throw err;
  }
  const json = await res.json();
  if (json.code !== 0) {
    const err = new Error(json.message || '上传失败');
    err.code = json.code;
    throw err;
  }
  return json.data;
}

export async function getCameraResult(taskId) {
  return request('/camera/result?task_id=' + encodeURIComponent(taskId));
}

export async function listCameraLogs(limit = 50, skip = 0) {
  return request(`/camera/logs?limit=${limit}&skip=${skip}`);
}