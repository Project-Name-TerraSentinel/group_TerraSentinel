// js/utils.js
// Utility functions for the TerraPulse frontend

/**
 * Escape HTML to prevent XSS attacks
 */
export function escapeHtml(str) {
  if (str == null) return '';
  return String(str).replace(/[&<>"']/g, (match) => {
    const escapeMap = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    };
    return escapeMap[match];
  });
}

/**
 * Compute priorities for parcels based on weighted factors
 */
export function computePriorities(featuresArray, weights = { deg: 0.6, area: 0.2, vuln: 0.2 }) {
  if (!Array.isArray(featuresArray) || featuresArray.length === 0) return [];

  // Clone features to avoid mutation
  const features = featuresArray.map(f => ({
    ...f,
    properties: { ...(f.properties || {}) }
  }));

  // Extract numeric values
  const toNum = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);
  const degradationScores = features.map(f => toNum(f.properties.score));
  const areas = features.map(f => toNum(f.properties.area_ha));
  const vulnerabilities = features.map(f => toNum(f.properties.vulnerability_index));

  // Find min/max for normalization
  const getMinMax = (arr) => {
    if (!Array.isArray(arr) || arr.length === 0) return { min: 0, max: 0 };
    const min = Math.min(...arr);
    const max = Math.max(...arr);
    return { min, max };
  };

  const degMinMax = getMinMax(degradationScores);
  const areaMinMax = getMinMax(areas);
  const vulnMinMax = getMinMax(vulnerabilities);

  // Normalize values to 0-1 range
  const normalize = (value, minMax) => {
    if (minMax.min === minMax.max) return 0;
    return Math.max(0, Math.min(1, (value - minMax.min) / (minMax.max - minMax.min)));
  };

  // Normalize weights
  const totalWeight = (weights.deg || 0) + (weights.area || 0) + (weights.vuln || 0) || 1;
  const normalizedWeights = {
    deg: (weights.deg || 0) / totalWeight,
    area: (weights.area || 0) / totalWeight,
    vuln: (weights.vuln || 0) / totalWeight
  };

  // Calculate priorities
  return features.map((feature, index) => {
    const degradationNorm = normalize(degradationScores[index], degMinMax);
    const areaNorm = normalize(areas[index], areaMinMax);
    const vulnNorm = normalize(vulnerabilities[index], vulnMinMax);

    const priority = Math.round(
      (normalizedWeights.deg * degradationNorm +
       normalizedWeights.area * areaNorm +
       normalizedWeights.vuln * vulnNorm) * 100
    );

    return {
      ...feature,
      properties: {
        ...feature.properties,
        priority
      }
    };
  });
}

/**
 * Compute degradation score from environmental factors
 */
export function computeDegradationScore({ 
  ndviTrend = 0, 
  rainfallDeficit = 0, 
  bareSoilIdx = 0 
} = {}) {
  const weights = { 
    ndvi: 0.5, 
    rain: 0.3, 
    bare: 0.2 
  };

  const safeNum = (n) => (Number.isFinite(Number(n)) ? Number(n) : 0);

  // Normalize NDVI trend (negative trend indicates degradation)
  const ndviNorm = Math.min(1, Math.max(0, -safeNum(ndviTrend) / 0.3));
  
  // Normalize rainfall deficit (0-1 range)
  const rainNorm = Math.min(1, Math.max(0, safeNum(rainfallDeficit)));
  
  // Normalize bare soil index (0-1 range)
  const bareNorm = Math.min(1, Math.max(0, safeNum(bareSoilIdx)));

  // Calculate weighted score (0-100)
  const score = Math.round(
    (weights.ndvi * ndviNorm + 
     weights.rain * rainNorm + 
     weights.bare * bareNorm) * 100
  );

  return score;
}

/**
 * Format numbers for display
 */
export function formatNumber(num, decimals = 1) {
  if (!Number.isFinite(num)) return '—';
  return Number(num).toFixed(decimals);
}

/**
 * Format coordinates for display
 */
export function formatCoordinates(lat, lon, decimals = 4) {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return 'Unknown location';
  return `${lat.toFixed(decimals)}, ${lon.toFixed(decimals)}`;
}

/**
 * Get risk level label from score
 */
export function getRiskLevel(score) {
  if (score >= 75) return { level: 'High', class: 'risk-high' };
  if (score >= 40) return { level: 'Medium', class: 'risk-medium' };
  return { level: 'Low', class: 'risk-low' };
}

/**
 * Debounce function calls
 */
export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}