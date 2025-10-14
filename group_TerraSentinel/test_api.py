#!/usr/bin/env python3
"""
Simple test script to verify the Terra Pulse API is working
"""

import requests
import json

# API configuration
API_BASE_URL = "http://localhost:5000"
API_KEY = "dev-key-123"

def test_basic_prediction():
    """Test the basic prediction endpoint"""
    url = f"{API_BASE_URL}/predict"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    # Sample NDVI data for testing
    data = {
        "ndvi_mean_early": 0.65,
        "ndvi_median_early": 0.67,
        "ndvi_std_early": 0.12,
        "ndvi_mean_late": 0.45,
        "ndvi_median_late": 0.47,
        "ndvi_std_late": 0.15,
        "ndvi_delta_mean": -0.20,
        "location": "Test Farm Field",
        "user_context": "API Testing"
    }
    
    try:
        print("Testing basic prediction endpoint...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"Error testing basic prediction: {e}")
        return False

def test_enhanced_prediction():
    """Test the enhanced prediction endpoint"""
    url = f"{API_BASE_URL}/enhanced-predict"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    # Sample data with user type for enhanced prediction
    data = {
        "ndvi_mean_early": 0.65,
        "ndvi_median_early": 0.67,
        "ndvi_std_early": 0.12,
        "ndvi_mean_late": 0.45,
        "ndvi_median_late": 0.47,
        "ndvi_std_late": 0.15,
        "ndvi_delta_mean": -0.20,
        "location": "Test Farm Field",
        "user_context": "API Testing",
        "user_type": "farmer"
    }
    
    try:
        print("\nTesting enhanced prediction endpoint...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"Error testing enhanced prediction: {e}")
        return False

def test_terra_pulse_health():
    """Test the Terra Pulse health endpoint"""
    url = f"{API_BASE_URL}/health/terra-pulse"
    
    try:
        print("\nTesting Terra Pulse health endpoint...")
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"Error testing Terra Pulse health: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Terra Pulse API...")
    print("=" * 50)
    
    # Test individual endpoints
    basic_ok = test_basic_prediction()
    enhanced_ok = test_enhanced_prediction()
    health_ok = test_terra_pulse_health()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"✅ Basic Prediction: {'PASS' if basic_ok else 'FAIL'}")
    print(f"✅ Enhanced Prediction: {'PASS' if enhanced_ok else 'FAIL'}")
    print(f"✅ Terra Pulse Health: {'PASS' if health_ok else 'FAIL'}")
    
    if basic_ok:
        print("\n🎉 API is working! Ready for frontend integration.")
        print("\nFrontend Integration Info:")
        print(f"API Base URL: {API_BASE_URL}")
        print(f"API Key: {API_KEY}")
        print("Available endpoints:")
        print("  - POST /predict (basic prediction)")
        print("  - POST /enhanced-predict (AI-enhanced prediction)")
        print("  - GET /health/terra-pulse (health check)")
    else:
        print("\n❌ API has issues. Check the backend logs.")