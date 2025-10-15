// js/terra_api.js
// TerraAPI client for frontend → backend communication

export const API_CONFIG = {
  // Update this to match your backend URL
  baseURL: "https://musical-fortnight-r4x5x66gvrqvcwqww-5000.app.github.dev",
  apiKey: "dev-test-key",
  timeoutMs: 30000
};

function getAuthToken() {
  try { return localStorage.getItem('tp_token'); } catch (e) { return null; }
}

async function fetchJsonWithTimeout(url, opts = {}, timeout = API_CONFIG.timeoutMs) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  
  try {
    const res = await fetch(url, { signal: controller.signal, ...opts });
    clearTimeout(id);
    
    const text = await res.text().catch(() => '');
    let data;
    try { 
      data = text ? JSON.parse(text) : {}; 
    } catch (e) { 
      data = text; 
    }
    
    if (!res.ok) {
      const msg = (data && data.error) ? data.error : 
                  (data && data.message) ? data.message : 
                  (typeof data === 'string' ? data : JSON.stringify(data));
      const err = new Error(`HTTP ${res.status}: ${msg}`);
      err.status = res.status;
      err.payload = data;
      throw err;
    }
    
    return data;
  } catch (err) {
    clearTimeout(id);
    if (err.name === 'AbortError') {
      throw new Error('Request timed out (server slow or unreachable)');
    }
    throw err;
  }
}

export class TerraAPI {
  constructor(cfg = {}) {
    this.baseURL = (cfg.baseURL || API_CONFIG.baseURL).replace(/\/$/, '');
    this.apiKey = cfg.apiKey || API_CONFIG.apiKey;
    this.timeoutMs = cfg.timeoutMs || API_CONFIG.timeoutMs;
  }

  _buildHeaders(extra = {}) {
    const token = getAuthToken();
    const headers = {
      'Content-Type': 'application/json',
      ...(this.apiKey ? { 'X-API-Key': this.apiKey } : {}),
      ...extra
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const cfg = {
      method: options.method || 'GET',
      headers: this._buildHeaders(options.headers || {}),
      body: options.body,
    };

    return await fetchJsonWithTimeout(url, cfg, this.timeoutMs);
  }

  // Basic prediction
  async predict(latitude, longitude) {
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      throw new Error('Invalid coordinates');
    }
    
    return this.request('/predict', {
      method: 'POST',
      body: JSON.stringify({ 
        latitude, 
        longitude, 
        user_context: 'frontend' 
      })
    });
  }

  // Enhanced prediction with AI
  async enhancedPredict(latitude, longitude, userType = 'farmer') {
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      throw new Error('Invalid coordinates');
    }
    
    return this.request('/enhanced-predict', {
      method: 'POST',
      body: JSON.stringify({ 
        latitude, 
        longitude, 
        user_context: 'frontend', 
        user_type: userType 
      })
    });
  }

  // AI Chat
  async chat(prompt, metadata = {}) {
    if (!prompt) throw new Error('Prompt required');
    
    return this.request('/ai', {
      method: 'POST',
      body: JSON.stringify({ prompt, metadata })
    });
  }

  // Health check
  async healthCheck() {
    return this.request('/health/system');
  }
}

// Default instance
export const api = new TerraAPI();
export default api;