// js/ui.js
import { escapeHtml } from './utils.js';

export function createUI(rootEl) {
  function renderLanding() {
    rootEl.innerHTML = `
      <div class="bg-white p-6 rounded-2xl shadow max-w-3xl w-full fade-in">
        <div class="flex items-start gap-6">
          <div class="flex-1">
            <h1 class="text-3xl font-bold mb-2 text-green-700">TerraPulse</h1>
            <p class="text-slate-600 mb-6">AI-powered soil degradation analysis for farmers and land planners. Get real-time insights and actionable recommendations.</p>
            
            <div class="grid-2 mb-6">
              <div class="p-4 border rounded-lg">
                <h3 class="font-semibold text-green-600 mb-2">🌱 For Farmers</h3>
                <p class="text-sm text-slate-600 mb-3">Get instant soil health alerts and personalized recommendations for your fields.</p>
                <button id="btnDemoFarmer" class="w-full py-2 px-4 bg-green-600 text-white rounded hover:bg-green-700">Try Farmer Demo</button>
              </div>
              
              <div class="p-4 border rounded-lg">
                <h3 class="font-semibold text-blue-600 mb-2">🗺️ For Planners</h3>
                <p class="text-sm text-slate-600 mb-3">Analyze regional degradation patterns and prioritize restoration efforts.</p>
                <button id="btnDemoPlanner" class="w-full py-2 px-4 bg-blue-600 text-white rounded hover:bg-blue-700">Try Planner Demo</button>
              </div>
            </div>
            
            <div class="flex gap-3 justify-center">
              <button id="btnSignIn" class="py-2 px-6 bg-sky-600 text-white rounded hover:bg-sky-700">Sign In</button>
              <button id="btnSignUp" class="py-2 px-6 border border-sky-600 text-sky-600 rounded hover:bg-sky-50">Sign Up</button>
            </div>
            
            <div class="mt-6 text-center">
              <div class="inline-flex items-center gap-2 text-sm text-slate-500">
                <span class="status-indicator status-online"></span>
                Connected to TerraPulse API
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function FarmerCard({ name, parcel, score, action, lastUpdated }) {
    const wrap = document.createElement('div');
    wrap.className = 'max-w-2xl mx-auto w-full fade-in';
    
    const riskClass = score >= 75 ? 'risk-high' : score >= 40 ? 'risk-medium' : 'risk-low';
    const riskLabel = score >= 75 ? 'High Risk' : score >= 40 ? 'Medium Risk' : 'Low Risk';
    
    wrap.innerHTML = `
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h2 class="text-2xl font-bold text-white">${escapeHtml(name)}</h2>
          <p class="text-green-100">Parcel: ${escapeHtml(parcel || '—')}</p>
        </div>
        <div class="flex gap-2">
          <button id="signOutBtn" class="btn-secondary">Sign Out</button>
          <button id="switchPlannerBtn" class="btn-secondary">Planner View</button>
        </div>
      </div>

      <div class="farmer-card">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h3 class="text-xl font-semibold">Field Analysis</h3>
            <p class="text-green-100 text-sm">Last updated: ${escapeHtml(lastUpdated || '')}</p>
          </div>
          <div class="text-right">
            <div id="farmerScore" class="risk-score ${riskClass}">${escapeHtml(String(score || '--'))}</div>
            <div class="text-green-100 text-sm">${riskLabel}</div>
          </div>
        </div>

        <!-- Live data section -->
        <div class="action-card mb-4">
          <div class="grid-2 gap-4 text-sm">
            <div>
              <strong>📍 Location:</strong><br>
              <span id="location" class="loading-spinner">Detecting...</span>
            </div>
            <div>
              <strong>⚠️ Risk Level:</strong><br>
              <span id="risk">Loading...</span>
            </div>
          </div>
          <div class="mt-3">
            <strong>💡 Recommendation:</strong><br>
            <span id="recommendation">Analyzing your field...</span>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="grid-3 gap-2 mb-4">
          <button id="saveBtn" class="btn-secondary">💾 Save</button>
          <button id="shareBtn" class="btn-secondary">📱 Share</button>
          <button id="reportBtn" class="btn-secondary">🚨 Report Issue</button>
        </div>

        <div class="flex items-center gap-3 mb-4">
          <button id="speakBtn" class="btn-secondary">🔊 Read Aloud</button>
          <button id="toggleMiniMap" class="btn-secondary">🗺️ Show Map</button>
        </div>

        <!-- Mini map (hidden by default) -->
        <div id="miniMapWrapper" class="hidden">
          <div id="miniMap" class="mini-map"></div>
        </div>

        <!-- Manual coordinates fallback -->
        <div id="manualLocation" class="hidden action-card">
          <p class="text-sm mb-3">📍 Can't detect location? Enter coordinates manually:</p>
          <div class="grid-2 gap-2 mb-3">
            <input id="manualLat" placeholder="Latitude" class="p-2 rounded border bg-white text-black" />
            <input id="manualLon" placeholder="Longitude" class="p-2 rounded border bg-white text-black" />
          </div>
          <button id="manualFetchBtn" class="btn-primary">Get Analysis</button>
        </div>
      </div>
    `;
    return wrap;
  }

  function renderPlannerShell(userName = 'Planner') {
    rootEl.innerHTML = `
      <div class="planner-shell fade-in">
        <div class="bg-white rounded-2xl shadow p-6">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h2 class="text-2xl font-bold text-blue-700">Land Restoration Planner</h2>
              <p class="text-slate-600">Welcome, ${escapeHtml(userName)} • Regional Analysis Dashboard</p>
            </div>
            <div class="flex gap-2">
              <button id="plannerSignOut" class="btn-secondary">Sign Out</button>
              <button id="openFarmerBtn" class="btn-secondary">Farmer View</button>
            </div>
          </div>

          <div class="grid gap-6" style="grid-template-columns: 1fr 350px;">
            <!-- Map Section -->
            <div>
              <div class="mb-4 flex items-center justify-between">
                <h3 class="font-semibold">Regional Overview</h3>
                <div class="flex items-center gap-4">
                  <label class="text-sm text-slate-600">Color by:</label>
                  <select id="colorMode" class="border p-2 rounded text-sm">
                    <option value="priority">Priority</option>
                    <option value="score">Degradation Score</option>
                    <option value="area">Area (ha)</option>
                  </select>
                </div>
              </div>
              <div id="plannerMap" class="map-container border rounded-lg"></div>
            </div>

            <!-- Controls Section -->
            <div class="space-y-6">
              <!-- Prioritization Controls -->
              <div class="bg-slate-50 p-4 rounded-lg">
                <h4 class="font-semibold mb-3">Prioritization Weights</h4>
                <div class="space-y-4">
                  <div>
                    <label class="text-sm text-slate-600">Degradation Risk</label>
                    <input id="wDeg" type="range" min="0" max="100" value="60" class="w-full"/>
                    <div class="text-xs text-slate-500">Value: <span id="wDegVal">60</span>%</div>
                  </div>
                  <div>
                    <label class="text-sm text-slate-600">Area Size</label>
                    <input id="wArea" type="range" min="0" max="100" value="20" class="w-full"/>
                    <div class="text-xs text-slate-500">Value: <span id="wAreaVal">20</span>%</div>
                  </div>
                  <div>
                    <label class="text-sm text-slate-600">Vulnerability</label>
                    <input id="wVuln" type="range" min="0" max="100" value="20" class="w-full"/>
                    <div class="text-xs text-slate-500">Value: <span id="wVulnVal">20</span>%</div>
                  </div>
                </div>
                <div class="mt-4 flex gap-2">
                  <button id="recomputeBtn" class="btn-primary text-sm">Recompute</button>
                  <input id="topN" type="number" min="1" value="5" class="w-16 border p-1 rounded text-sm"/>
                  <button id="selectTopBtn" class="btn-secondary text-sm">Select Top</button>
                </div>
              </div>

              <!-- Parcel List -->
              <div class="bg-slate-50 p-4 rounded-lg">
                <h4 class="font-semibold mb-3">Priority Parcels</h4>
                <div id="topList" class="space-y-2 max-h-48 overflow-auto text-sm"></div>
              </div>

              <!-- Restoration Plan -->
              <div class="bg-slate-50 p-4 rounded-lg">
                <h4 class="font-semibold mb-3">Restoration Plan</h4>
                <div id="planList" class="space-y-2 max-h-32 overflow-auto text-sm"></div>
                <div class="mt-3 flex gap-2">
                  <button id="addSelectedBtn" class="btn-primary text-sm flex-1">Add Selected</button>
                  <button id="exportCsvBtn" class="btn-secondary text-sm">Export CSV</button>
                </div>
                <div class="mt-2 text-xs text-slate-500">
                  Plan size: <span id="planCount">0</span> parcels
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Event delegation
  function attachDelegation() {
    rootEl.addEventListener('click', (e) => {
      const target = e.target;
      
      if (target.matches('#btnSignIn') || target.matches('#btnSignUp')) {
        const mode = target.id === 'btnSignIn' ? 'signin' : 'signup';
        rootEl.dispatchEvent(new CustomEvent('ui:open-auth', { detail: { mode } }));
      } else if (target.matches('#btnDemoPlanner')) {
        rootEl.dispatchEvent(new CustomEvent('ui:demo-planner'));
      } else if (target.matches('#btnDemoFarmer')) {
        rootEl.dispatchEvent(new CustomEvent('ui:demo-farmer'));
      } else if (target.matches('#signOutBtn') || target.matches('#plannerSignOut')) {
        rootEl.dispatchEvent(new CustomEvent('ui:signout'));
      } else if (target.matches('#switchPlannerBtn') || target.matches('#openFarmerBtn')) {
        rootEl.dispatchEvent(new CustomEvent('ui:switch-role'));
      }
    });
  }

  attachDelegation();
  
  return { 
    renderLanding, 
    FarmerCard, 
    renderPlannerShell 
  };
}