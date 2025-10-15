// js/auth.js
// Authentication module for TerraPulse

const TOKEN_KEY = 'terrapulse_token';
const USER_KEY = 'terrapulse_user';

/**
 * Simple JWT payload parser (for demo purposes)
 */
function parseJwtPayload(token) {
  if (!token) return null;
  
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const decoded = atob(payload);
    return JSON.parse(decodeURIComponent(escape(decoded)));
  } catch (error) {
    console.warn('Failed to parse JWT payload:', error);
    return null;
  }
}

/**
 * Save authentication token
 */
function saveToken(token) {
  if (!token) {
    localStorage.removeItem(TOKEN_KEY);
  } else {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

/**
 * Save user data
 */
function saveUser(user) {
  if (!user) {
    localStorage.removeItem(USER_KEY);
  } else {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
}

export const Auth = {
  /**
   * Get stored authentication token
   */
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  /**
   * Get stored user data
   */
  getUser() {
    try {
      const userData = localStorage.getItem(USER_KEY);
      return userData ? JSON.parse(userData) : null;
    } catch (error) {
      console.error('Failed to parse user data:', error);
      return null;
    }
  },

  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    return !!this.getToken();
  },

  /**
   * Get authorization header for API requests
   */
  getAuthHeader() {
    const token = this.getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  },

  /**
   * Parse user from JWT token
   */
  parseUserFromToken() {
    const token = this.getToken();
    if (!token) return null;
    
    const payload = parseJwtPayload(token);
    if (!payload) return null;
    
    // Return user data from token payload
    return payload.user || payload;
  },

  /**
   * Sign up new user (demo implementation)
   */
  async signUp({ name, email, password, role = 'farmer', parcel_id = null }) {
    // For demo purposes, create a mock user
    const user = {
      id: `user_${Date.now()}`,
      name,
      email,
      role,
      parcel_id,
      created_at: new Date().toISOString()
    };

    // Generate a mock token
    const token = `demo_token_${Date.now()}`;
    
    // Save to localStorage
    saveToken(token);
    saveUser(user);
    
    return user;
  },

  /**
   * Sign in existing user (demo implementation)
   */
  async signIn(email, password) {
    // For demo purposes, create a mock user based on email
    const user = {
      id: `user_${email.replace('@', '_').replace('.', '_')}`,
      name: email.split('@')[0],
      email,
      role: 'farmer',
      parcel_id: 'P-001',
      lat: 0.52,
      lng: 36.08
    };

    // Generate a mock token
    const token = `demo_token_${Date.now()}`;
    
    // Save to localStorage
    saveToken(token);
    saveUser(user);
    
    return user;
  },

  /**
   * Sign out user
   */
  async signOut() {
    saveToken(null);
    saveUser(null);
    return true;
  },

  /**
   * Refresh authentication token
   */
  async refreshToken() {
    // For demo purposes, just return the existing token
    return this.getToken();
  },

  /**
   * Check if token is expired
   */
  isTokenExpired() {
    const token = this.getToken();
    if (!token) return true;
    
    const payload = parseJwtPayload(token);
    if (!payload || !payload.exp) return false;
    
    const now = Math.floor(Date.now() / 1000);
    return payload.exp < now;
  }
};