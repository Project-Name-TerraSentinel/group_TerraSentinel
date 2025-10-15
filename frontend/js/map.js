// js/map.js
// Map utilities for TerraPulse using Leaflet

import { escapeHtml } from './utils.js';

/**
 * Create a Leaflet map instance
 */
export function createMap(containerId = 'plannerMap') {
  // Initialize map centered on Kenya
  const map = L.map(containerId).setView([0.52, 36.1], 12);
  
  // Add OpenStreetMap tiles
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors'
  }).addTo(map);

  let currentLayer = null;

  /**
   * Get color based on priority level
   */
  function getColorByPriority(priority) {
    if (priority >= 80) return '#dc2626'; // High priority - red
    if (priority >= 60) return '#ea580c'; // Medium-high - orange
    if (priority >= 40) return '#d97706'; // Medium - amber
    if (priority >= 20) return '#65a30d'; // Low-medium - lime
    return '#16a34a'; // Low priority - green
  }

  /**
   * Get color based on degradation score
   */
  function getColorByScore(score) {
    if (score >= 75) return '#ef4444'; // High risk - red
    if (score >= 40) return '#f59e0b'; // Medium risk - yellow
    return '#10b981'; // Low risk - green
  }

  /**
   * Get color based on area size
   */
  function getColorByArea(area) {
    if (area > 5) return '#dc2626'; // Large area - red
    if (area > 2) return '#f59e0b'; // Medium area - yellow
    return '#10b981'; // Small area - green
  }

  return {
    map,

    /**
     * Render GeoJSON data on the map
     */
    renderGeoJson(geojson, options = {}) {
      const { colorMode = 'priority', onFeatureAction = null } = options;

      // Remove existing layer
      if (currentLayer) {
        currentLayer.remove();
      }

      // Create new GeoJSON layer
      currentLayer = L.geoJSON(geojson, {
        style(feature) {
          const props = feature.properties || {};
          let fillColor = '#ddd';

          // Determine color based on mode
          switch (colorMode) {
            case 'priority':
              fillColor = getColorByPriority(Number(props.priority || 0));
              break;
            case 'score':
              fillColor = getColorByScore(Number(props.score || 0));
              break;
            case 'area':
              fillColor = getColorByArea(Number(props.area_ha || 0));
              break;
            default:
              fillColor = '#ddd';
          }

          return {
            color: '#333',
            weight: 2,
            fillColor: fillColor,
            fillOpacity: 0.7,
            opacity: 1
          };
        },

        onEachFeature(feature, layer) {
          const props = feature.properties || {};
          
          // Create popup content
          const popupContent = `
            <div style="min-width: 250px; font-family: system-ui;">
              <h4 style="margin: 0 0 8px 0; color: #1f2937; font-size: 16px;">
                ${escapeHtml(props.id || 'Unknown Parcel')}
              </h4>
              
              <div style="margin-bottom: 12px; font-size: 14px; color: #4b5563;">
                <div><strong>Owner:</strong> ${escapeHtml(props.owner || 'Unknown')}</div>
                <div><strong>Degradation Score:</strong> ${escapeHtml(String(props.score ?? '—'))}</div>
                <div><strong>Area:</strong> ${escapeHtml(String(props.area_ha ?? '—'))} ha</div>
                <div><strong>Vulnerability:</strong> ${escapeHtml(String(props.vulnerability_index ?? '—'))}</div>
                <div><strong>Priority:</strong> ${escapeHtml(String(props.priority ?? '—'))}</div>
              </div>
              
              ${props.recommended_action ? `
                <div style="margin-bottom: 12px; padding: 8px; background: #f3f4f6; border-radius: 4px; font-size: 13px;">
                  <strong>Recommendation:</strong><br>
                  ${escapeHtml(props.recommended_action)}
                </div>
              ` : ''}
              
              <div style="display: flex; gap: 8px; margin-top: 12px;">
                <button class="popup-select" data-id="${escapeHtml(props.id || '')}" 
                        style="padding: 4px 8px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
                  Select
                </button>
                <button class="popup-add-plan" data-id="${escapeHtml(props.id || '')}"
                        style="padding: 4px 8px; background: #10b981; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
                  Add to Plan
                </button>
              </div>
            </div>
          `;

          // Bind popup
          layer.bindPopup(popupContent, {
            maxWidth: 300,
            className: 'terrapulse-popup'
          });

          // Handle popup events
          layer.on('popupopen', (event) => {
            if (onFeatureAction) {
              onFeatureAction(feature, event);
            }
          });

          // Add hover effects
          layer.on('mouseover', function() {
            this.setStyle({
              weight: 3,
              opacity: 1,
              fillOpacity: 0.9
            });
          });

          layer.on('mouseout', function() {
            this.setStyle({
              weight: 2,
              opacity: 1,
              fillOpacity: 0.7
            });
          });
        }
      }).addTo(map);

      // Fit map to layer bounds
      try {
        if (currentLayer && currentLayer.getBounds && !currentLayer.getBounds().isEmpty()) {
          map.fitBounds(currentLayer.getBounds(), { padding: [20, 20] });
        }
      } catch (error) {
        console.warn('Could not fit map to bounds:', error);
      }
    },

    /**
     * Add a marker to the map
     */
    addMarker(lat, lng, options = {}) {
      const { popup, icon } = options;
      
      const marker = L.marker([lat, lng]);
      
      if (icon) {
        marker.setIcon(icon);
      }
      
      if (popup) {
        marker.bindPopup(popup);
      }
      
      marker.addTo(map);
      return marker;
    },

    /**
     * Clear all layers from the map
     */
    clearLayers() {
      if (currentLayer) {
        currentLayer.remove();
        currentLayer = null;
      }
    },

    /**
     * Set map view to specific coordinates
     */
    setView(lat, lng, zoom = 13) {
      map.setView([lat, lng], zoom);
    },

    /**
     * Get current map bounds
     */
    getBounds() {
      return map.getBounds();
    },

    /**
     * Fit map to specific bounds
     */
    fitBounds(bounds, options = {}) {
      map.fitBounds(bounds, options);
    }
  };
}