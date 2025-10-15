// js/main.js
// Main app wiring: UI routing, farmer/planner screens, integration with backend via TerraAPI.

import { createUI } from './ui.js';
import { createMap } from './map.js';
import { computePriorities, computeDegradationScore, escapeHtml } from './utils.js';
import { Storage } from './storage.js';
import { Auth } from './auth.js';
import { getUserLocation } from './location.js';
import { TerraAPI } from './terra_api.js';

const api = new TerraAPI();
const root = document.getElementById('app');
const ui = createUI(root);

// App state container
const AppState = {
  user: null,
  geojson: null,
  selectedIds: new Set(),
  restorationPlan: Storage.loadPlan()
};

let mapApi = null;

// ROUTER: decides which screen to show after login or on app start
export function routeAfterLogin(profile) {
  if (!profile) {
    ui.renderLanding();
    return;
  }
  if (profile.role === 'farmer') renderFarmerScreen(profile);
  else renderPlannerScreen(profile);
}
window.routeAfterLogin = routeAfterLogin;

// Initialize app
(async function init() {
  let user = null;
  try {
    if (Auth && typeof Auth.parseUserFromToken === 'function') {
      user = Auth.parseUserFromToken();
    }
  } catch (err) {
    console.warn('Auth restore skipped', err);
  }

  if (user) {
    AppState.user = user;
    routeAfterLogin(user);
  } else {
    ui.renderLanding();
  }
})();

// AUTH MODAL
function showAuthModal(mode = 'signin') {
  const modal = document.getElementById('authModal');
  if (!modal) return;
  
  const title = document.getElementById('authTitle');
  const signupFields = document.getElementById('signupFields');
  const roleWrapper = document.getElementById('roleWrapper');
  const nameInput = document.getElementById('nameInput');
  const emailInput = document.getElementById('emailInput');
  const passwordInput = document.getElementById('passwordInput');
  const roleSelect = document.getElementById('roleSelect');
  const parcelInput = document.getElementById('parcelInput');
  const authMsg = document.getElementById('authMsg');

  // Reset form
  authMsg.textContent = '';
  emailInput.value = '';
  passwordInput.value = '';
  nameInput.value = '';
  parcelInput.value = '';
  roleSelect.value = '';

  if (mode === 'signin') {
    title.textContent = 'Sign in';
    signupFields.classList.add('hidden');
    roleWrapper.classList.add('hidden');
  } else {
    title.textContent = 'Sign up';
    signupFields.classList.remove('hidden');
    roleWrapper.classList.remove('hidden');
  }

  modal.style.display = 'flex';

  const cancel = document.getElementById('authCancel');
  const authSubmit = document.getElementById('authSubmit');

  function cleanup() {
    modal.style.display = 'none';
    cancel.removeEventListener('click', onCancel);
    authSubmit.removeEventListener('click', onSubmit);
  }

  function onCancel() {
    cleanup();
  }

  async function onSubmit() {
    authMsg.textContent = '';
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    
    if (!email || !password) {
      authMsg.textContent = 'Please provide email and password';
      return;
    }

    try {
      let user = null;
      if (mode === 'signin') {
        // For demo purposes, create a mock user
        user = { 
          id: 'demo-user', 
          name: email.split('@')[0], 
          email: email, 
          role: 'farmer',
          parcel_id: 'P-001',
          lat: 0.52,
          lng: 36.08
        };
      } else {
        const name = nameInput.value.trim();
        const role = roleSelect.value;
        const parcel = parcelInput.value.trim() || null;
        
        if (!role) {
          authMsg.textContent = 'Please choose a role';
          return;
        }
        
        user = {
          id: 'demo-user',
          name: name,
          email: email,
          role: role,
          parcel_id: parcel,
          lat: 0.52,
          lng: 36.08
        };
      }

      AppState.user = user;
      cleanup();
      routeAfterLogin(user);
    } catch (err) {
      authMsg.textContent = err.message || 'Authentication failed';
    }
  }

  cancel.addEventListener('click', onCancel);
  authSubmit.addEventListener('click', onSubmit);

  roleSelect.addEventListener('change', (e) => {
    if (e.target.value === 'farmer') {
      parcelInput.classList.remove('hidden');
    } else {
      parcelInput.classList.add('hidden');
    }
  });
}

// EVENT HANDLERS
root.addEventListener('ui:open-auth', (e) => showAuthModal(e.detail.mode));
root.addEventListener('ui:demo-planner', () => {
  const u = { id: 'demo-planner', name: 'Planner Demo', email: 'planner@demo', role: 'planner' };
  AppState.user = u;
  renderPlannerScreen(u);
});
root.addEventListener('ui:demo-farmer', () => {
  const u = { id: 'demo-farmer', name: 'Grace Demo', email: 'grace@demo', role: 'farmer', parcel_id: 'P-001', lat: 0.52, lng: 36.08 };
  AppState.user = u;
  renderFarmerScreen(u);
});
root.addEventListener('ui:signout', () => {
  AppState.user = null;
  ui.renderLanding();
});
root.addEventListener('ui:switch-role', () => {
  if (AppState.user && AppState.user.role === 'farmer') renderPlannerScreen(AppState.user);
  else if (AppState.user && AppState.user.role === 'planner') renderFarmerScreen(AppState.user);
  else ui.renderLanding();
});

// FARMER PREDICTION LOGIC
export async function fetchAndShowPredictionForFarmer(profile) {
  console.log('Fetching prediction for farmer', profile);

  const locEl = document.getElementById('location');
  const riskEl = document.getElementById('risk');
  const recEl = document.getElementById('recommendation');

  if (locEl) locEl.textContent = 'Detecting location...';
  if (riskEl) riskEl.textContent = 'Loading...';
  if (recEl) recEl.textContent = 'Analyzing...';

  try {
    // Get location
    let latitude = null, longitude = null;
    try {
      const pos = await getUserLocation({ enableHighAccuracy: false, timeout: 15000 });
      latitude = Number(pos.latitude);
      longitude = Number(pos.longitude);
      console.log('Got location', { latitude, longitude });
    } catch (locErr) {
      console.warn('Geolocation failed, using fallback', locErr);
      if (profile && (profile.lat || profile.latitude) && (profile.lng || profile.longitude)) {
        latitude = Number(profile.lat || profile.latitude);
        longitude = Number(profile.lng || profile.longitude);
      }
    }

    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      if (locEl) locEl.textContent = 'Location unavailable';
      if (recEl) recEl.textContent = 'Enter coordinates manually';
      const manual = document.getElementById('manualLocation');
      if (manual) manual.classList.remove('hidden');
      return;
    }

    // Call backend API
    let resp;
    try {
      resp = await api.predict(latitude, longitude);
      console.log('API response', resp);
    } catch (err) {
      console.error('API call failed', err);
      throw err;
    }

    // Update UI
    const place = resp.location || `(${latitude.toFixed(5)}, ${longitude.toFixed(5)})`;
    const score = resp.degradation_risk_score ?? resp.score ?? null;
    const action = resp.recommended_action || resp.recommendation || '';

    if (locEl) locEl.textContent = place;
    if (riskEl) riskEl.textContent = (score !== null ? `${score}%` : '—');
    if (recEl) recEl.textContent = action || 'No recommendation available';

    // Update map if available
    try {
      if (window._miniMapInstance && typeof L !== 'undefined') {
        const m = window._miniMapInstance;
        if (m) {
          L.marker([latitude, longitude]).addTo(m)
            .bindPopup(`${place} — Risk ${score}%`)
            .openPopup();
        }
      }
    } catch (e) { /* non-fatal */ }

    console.log('Prediction completed successfully');
  } catch (err) {
    console.error('Prediction error:', err);
    if (locEl) locEl.textContent = 'Location unavailable';
    if (riskEl) riskEl.textContent = '—';
    if (recEl) recEl.textContent = 'Could not fetch recommendation';
    const manual = document.getElementById('manualLocation');
    if (manual) manual.classList.remove('hidden');
  }
}

// FARMER SCREEN
function renderFarmerScreen(profile) {
  const cardEl = ui.FarmerCard({
    name: profile?.name || 'Farmer',
    parcel: profile?.parcel_id || 'demo',
    score: 78,
    action: 'Try mulching with crop residue this week.',
    lastUpdated: new Date().toLocaleString()
  });
  
  root.innerHTML = '';
  root.appendChild(cardEl);

  // Wire up event handlers
  document.getElementById('signOutBtn')?.addEventListener('click', () => {
    AppState.user = null;
    ui.renderLanding();
  });
  
  document.getElementById('switchPlannerBtn')?.addEventListener('click', () => {
    renderPlannerScreen(profile);
  });

  // Action buttons
  document.getElementById('saveBtn')?.addEventListener('click', () => {
    toast('Saved locally');
  });
  
  document.getElementById('shareBtn')?.addEventListener('click', () => {
    const txt = `TerraPulse: Risk ${document.getElementById('risk')?.textContent}. ${document.getElementById('recommendation')?.textContent}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(txt)}`, '_blank');
  });
  
  document.getElementById('reportBtn')?.addEventListener('click', () => {
    const comment = prompt('Why is this alert false? (optional)');
    if (comment !== null) {
      toast('Reported (queued locally)');
    }
  });

  // Text-to-speech
  document.getElementById('speakBtn')?.addEventListener('click', () => {
    const text = document.getElementById('recommendation')?.textContent || '';
    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'en-US';
      utterance.rate = 0.95;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    } else {
      alert('Speech not supported in this browser');
    }
  });

  // Mini-map toggle
  document.getElementById('toggleMiniMap')?.addEventListener('click', () => {
    const wrapper = document.getElementById('miniMapWrapper');
    if (!wrapper) return;
    
    if (wrapper.classList.contains('hidden')) {
      wrapper.classList.remove('hidden');
      if (!window._miniMapInitFarmer) {
        const lat = profile?.lat || 0.52;
        const lng = profile?.lng || 36.08;
        const map = L.map('miniMap', { zoomControl: false }).setView([lat, lng], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
        L.marker([lat, lng]).addTo(map).bindPopup('Your field').openPopup();
        window._miniMapInitFarmer = true;
        window._miniMapInstance = map;
      }
    } else {
      wrapper.classList.add('hidden');
    }
  });

  // Manual coordinates
  const manualFetchBtn = document.getElementById('manualFetchBtn');
  if (manualFetchBtn) {
    manualFetchBtn.addEventListener('click', async () => {
      const lat = parseFloat(document.getElementById('manualLat')?.value);
      const lon = parseFloat(document.getElementById('manualLon')?.value);
      
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        alert('Please enter valid coordinates');
        return;
      }
      
      try {
        const data = await api.predict(lat, lon);
        document.getElementById('location').textContent = data.location || `(${lat.toFixed(5)}, ${lon.toFixed(5)})`;
        document.getElementById('risk').textContent = data.degradation_risk_score ?? data.score ?? '--';
        document.getElementById('recommendation').textContent = data.recommended_action || 'No recommendation';
        
        if (window._miniMapInstance && typeof L !== 'undefined') {
          L.marker([lat, lon]).addTo(window._miniMapInstance)
            .bindPopup(`Manual: Risk ${data.degradation_risk_score ?? '—'}`)
            .openPopup();
        }
      } catch (e) {
        console.error('Manual fetch failed', e);
        alert('Could not fetch data for entered coordinates');
      }
    });
  }

  // Fetch live prediction
  fetchAndShowPredictionForFarmer(profile);
}

// PLANNER SCREEN (simplified)
function renderPlannerScreen(profile) {
  ui.renderPlannerShell(profile?.name || 'Officer');
  
  document.getElementById('plannerSignOut')?.addEventListener('click', () => {
    AppState.user = null;
    ui.renderLanding();
  });
  
  document.getElementById('openFarmerBtn')?.addEventListener('click', () => {
    renderFarmerScreen(profile);
  });

  // Initialize map after a short delay
  setTimeout(() => {
    mapApi = createMap('plannerMap');
    // Add some demo data for the planner view
    const demoGeoJSON = {
      "type": "FeatureCollection",
      "features": [
        {
          "type": "Feature",
          "properties": {
            "id": "P-001",
            "owner": "John Farmer",
            "score": 75,
            "area_ha": 2.5,
            "vulnerability_index": 0.8,
            "priority": 85,
            "recommended_action": "Apply mulch and reduce tillage"
          },
          "geometry": {
            "type": "Polygon",
            "coordinates": [[
              [36.08, 0.52],
              [36.09, 0.52],
              [36.09, 0.53],
              [36.08, 0.53],
              [36.08, 0.52]
            ]]
          }
        }
      ]
    };
    
    AppState.geojson = demoGeoJSON;
    if (mapApi && typeof mapApi.renderGeoJson === 'function') {
      mapApi.renderGeoJson(AppState.geojson, { colorMode: 'priority' });
    }
  }, 100);
}

// UTILITY FUNCTIONS
function toast(msg) {
  const toast = document.createElement('div');
  toast.textContent = msg;
  toast.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: rgba(0,0,0,0.85);
    color: white;
    padding: 8px 12px;
    border-radius: 6px;
    z-index: 9999;
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2000);
}

window.App = { routeAfterLogin };