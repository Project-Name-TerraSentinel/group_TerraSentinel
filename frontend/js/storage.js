// js/storage.js
// Local storage utilities for TerraPulse

const STORAGE_KEYS = {
  PENDING_REPORTS: 'terrapulse_pending_reports',
  RESTORATION_PLAN: 'terrapulse_restoration_plan',
  USERS: 'terrapulse_users',
  USER_PREFERENCES: 'terrapulse_preferences'
};

export const Storage = {
  // Pending reports management
  savePendingReport(report) {
    try {
      const reports = this.getPendingReports();
      reports.push({
        ...report,
        id: Date.now().toString(),
        timestamp: new Date().toISOString()
      });
      localStorage.setItem(STORAGE_KEYS.PENDING_REPORTS, JSON.stringify(reports));
      return true;
    } catch (error) {
      console.error('Failed to save pending report:', error);
      return false;
    }
  },

  getPendingReports() {
    try {
      const reports = localStorage.getItem(STORAGE_KEYS.PENDING_REPORTS);
      return reports ? JSON.parse(reports) : [];
    } catch (error) {
      console.error('Failed to load pending reports:', error);
      return [];
    }
  },

  clearPendingReports() {
    try {
      localStorage.removeItem(STORAGE_KEYS.PENDING_REPORTS);
      return true;
    } catch (error) {
      console.error('Failed to clear pending reports:', error);
      return false;
    }
  },

  // Restoration plan management
  savePlan(plan) {
    try {
      localStorage.setItem(STORAGE_KEYS.RESTORATION_PLAN, JSON.stringify(plan));
      return true;
    } catch (error) {
      console.error('Failed to save restoration plan:', error);
      return false;
    }
  },

  loadPlan() {
    try {
      const plan = localStorage.getItem(STORAGE_KEYS.RESTORATION_PLAN);
      return plan ? JSON.parse(plan) : [];
    } catch (error) {
      console.error('Failed to load restoration plan:', error);
      return [];
    }
  },

  // User management (for demo purposes)
  saveUsers(users) {
    try {
      localStorage.setItem(STORAGE_KEYS.USERS, JSON.stringify(users));
      return true;
    } catch (error) {
      console.error('Failed to save users:', error);
      return false;
    }
  },

  loadUsers() {
    try {
      const users = localStorage.getItem(STORAGE_KEYS.USERS);
      return users ? JSON.parse(users) : [];
    } catch (error) {
      console.error('Failed to load users:', error);
      return [];
    }
  },

  // User preferences
  savePreferences(preferences) {
    try {
      localStorage.setItem(STORAGE_KEYS.USER_PREFERENCES, JSON.stringify(preferences));
      return true;
    } catch (error) {
      console.error('Failed to save preferences:', error);
      return false;
    }
  },

  loadPreferences() {
    try {
      const prefs = localStorage.getItem(STORAGE_KEYS.USER_PREFERENCES);
      return prefs ? JSON.parse(prefs) : {
        language: 'en',
        units: 'metric',
        notifications: true
      };
    } catch (error) {
      console.error('Failed to load preferences:', error);
      return {
        language: 'en',
        units: 'metric',
        notifications: true
      };
    }
  },

  // Clear all data
  clearAll() {
    try {
      Object.values(STORAGE_KEYS).forEach(key => {
        localStorage.removeItem(key);
      });
      return true;
    } catch (error) {
      console.error('Failed to clear storage:', error);
      return false;
    }
  }
};