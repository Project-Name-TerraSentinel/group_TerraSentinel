// js/location.js
// Geolocation utilities for TerraPulse

/**
 * Get user's current location using the Geolocation API
 */
export function getUserLocation(options = {}) {
  const defaultOptions = {
    enableHighAccuracy: false,
    timeout: 15000,
    maximumAge: 300000 // 5 minutes
  };

  const finalOptions = { ...defaultOptions, ...options };

  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation is not supported by this browser'));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: position.timestamp
        });
      },
      (error) => {
        let message = 'Unable to get location';
        
        switch (error.code) {
          case error.PERMISSION_DENIED:
            message = 'Location access denied by user';
            break;
          case error.POSITION_UNAVAILABLE:
            message = 'Location information unavailable';
            break;
          case error.TIMEOUT:
            message = 'Location request timed out';
            break;
          default:
            message = error.message || 'Unknown location error';
            break;
        }
        
        reject(new Error(message));
      },
      finalOptions
    );
  });
}

/**
 * Watch user's location for changes
 */
export function watchUserLocation(callback, options = {}) {
  const defaultOptions = {
    enableHighAccuracy: false,
    timeout: 15000,
    maximumAge: 300000
  };

  const finalOptions = { ...defaultOptions, ...options };

  if (!navigator.geolocation) {
    callback(new Error('Geolocation is not supported by this browser'), null);
    return null;
  }

  const watchId = navigator.geolocation.watchPosition(
    (position) => {
      callback(null, {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        timestamp: position.timestamp
      });
    },
    (error) => {
      let message = 'Unable to watch location';
      
      switch (error.code) {
        case error.PERMISSION_DENIED:
          message = 'Location access denied by user';
          break;
        case error.POSITION_UNAVAILABLE:
          message = 'Location information unavailable';
          break;
        case error.TIMEOUT:
          message = 'Location request timed out';
          break;
        default:
          message = error.message || 'Unknown location error';
          break;
      }
      
      callback(new Error(message), null);
    },
    finalOptions
  );

  return watchId;
}

/**
 * Stop watching user's location
 */
export function clearLocationWatch(watchId) {
  if (navigator.geolocation && watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
  }
}

/**
 * Check if geolocation is supported and permitted
 */
export async function checkLocationPermission() {
  if (!navigator.geolocation) {
    return { supported: false, permitted: false };
  }

  if (!navigator.permissions) {
    return { supported: true, permitted: 'unknown' };
  }

  try {
    const permission = await navigator.permissions.query({ name: 'geolocation' });
    return {
      supported: true,
      permitted: permission.state === 'granted',
      state: permission.state
    };
  } catch (error) {
    return { supported: true, permitted: 'unknown' };
  }
}

/**
 * Calculate distance between two coordinates (Haversine formula)
 */
export function calculateDistance(lat1, lon1, lat2, lon2) {
  const R = 6371; // Earth's radius in kilometers
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const distance = R * c;
  
  return distance; // Distance in kilometers
}

function toRadians(degrees) {
  return degrees * (Math.PI / 180);
}