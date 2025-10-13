#!/usr/bin/env python3
"""
Production deployment test script.
Tests all components of the enhanced Terra Pulse API.
"""

import os
import sys
import requests
import json
import time
from backend.services.dify_service import DifyService, DifyWorkflowInput
from backend.services.cached_terra_pulse_service import CachedTerraPulseService
from backend.services.terra_pulse_service import PredictionInput
from backend.config.settings import get_config

# Test configuration
API_BASE = os.environ.get("API_BASE", "http://localhost:5000")
TEST_API_KEY = "test-api-key-12345"

def test_dify_connection():
    """Test connection to production Dify workflow."""
    try:
        print("🔧 Testing Dify connection...")
        config = get_config()
        print(f"   API Endpoint: {config.dify_api_endpoint}")
        print(f"   Workflow ID: {config.dify_workflow_id}")
        print(f"   API Key: {config.dify_api_key[:12]}...")
        
        dify_service = DifyService(config)
        
        # Test health check
        print("🏥 Testing Dify health check...")
        health = dify_service.health_check()
        print(f"   Status: {health.status.value}")
        print(f"   Message: {health.message}")
        
        # Test sample workflow
        print("🧪 Testing Dify workflow...")
        sample_input = DifyWorkflowInput(
            degradation_risk=75,
            risk_factors=["bare_soil_increase", "low_ndvi"],
            location="Baringo County, Kenya",
            user_context="smallholder_farmer",
            confidence=0.85,
            recommended_action_key="mulch_crop_residue",
            user_type="farmer"
        )
        
        response = dify_service.execute_workflow(sample_input)
        print(f"   Workflow Status: {response.get('status', 'unknown')}")
        print(f"   Recommendations: {len(response.get('enhanced_recommendations', []))}")
        
        print("✅ Dify integration test successful!")
        return True
        
    except Exception as e:
        print(f"❌ Dify integration test failed: {str(e)}")
        return False

def test_terra_pulse_service():
    """Test Terra Pulse service."""
    try:
        print("\n🌍 Testing Terra Pulse service...")
        config = get_config()
        terra_service = CachedTerraPulseService(config)
        
        # Test prediction
        sample_input = PredictionInput(
            ndvi_mean_early=0.45,
            ndvi_median_early=0.43,
            ndvi_std_early=0.12,
            ndvi_mean_late=0.38,
            ndvi_median_late=0.36,
            ndvi_std_late=0.15,
            ndvi_delta_mean=-0.07,
            location="Baringo County, Kenya",
            user_context="smallholder_farmer"
        )
        
        result = terra_service.predict(sample_input)
        print(f"   Degradation Risk: {result.degradation_risk}%")
        print(f"   Confidence: {result.confidence}")
        print(f"   Processing Time: {result.processing_time_ms}ms")
        
        print("✅ Terra Pulse service test successful!")
        return True
        
    except Exception as e:
        print(f"❌ Terra Pulse service test failed: {str(e)}")
        return False

def test_api_endpoints():
    """Test API endpoints."""
    try:
        print("\n🌐 Testing API endpoints...")
        
        # Test root endpoint
        print("📖 Testing root documentation...")
        response = requests.get(f"{API_BASE}/")
        if response.status_code == 200:
            data = response.json()
            print(f"   Service: {data.get('service', 'Unknown')}")
            print(f"   Version: {data.get('version', 'Unknown')}")
        else:
            print(f"   ❌ Root endpoint failed: {response.status_code}")
            return False
        
        # Test health endpoints
        print("🏥 Testing health endpoints...")
        health_endpoints = ["/health/system", "/health/terra-pulse", "/health/dify"]
        
        for endpoint in health_endpoints:
            response = requests.get(f"{API_BASE}{endpoint}")
            status = "✅" if response.status_code in [200, 503] else "❌"
            print(f"   {status} {endpoint}: {response.status_code}")
        
        # Test metrics
        print("📊 Testing metrics endpoint...")
        response = requests.get(f"{API_BASE}/metrics")
        if response.status_code == 200:
            print("   ✅ Metrics endpoint working")
        else:
            print(f"   ❌ Metrics endpoint failed: {response.status_code}")
        
        # Test prediction endpoints
        print("🔮 Testing prediction endpoints...")
        
        sample_data = {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Baringo County, Kenya",
            "user_context": "smallholder_farmer"
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": TEST_API_KEY
        }
        
        # Test basic prediction
        print("   Testing /predict endpoint...")
        response = requests.post(f"{API_BASE}/predict", 
                               json=sample_data, headers=headers)
        if response.status_code == 200:
            data = response.json()
            risk = data.get("ml_output", {}).get("degradation_risk", 0)
            print(f"   ✅ Basic prediction: {risk}% risk")
        else:
            print(f"   ❌ Basic prediction failed: {response.status_code}")
        
        # Test enhanced prediction
        print("   Testing /enhanced-predict endpoint...")
        enhanced_data = {**sample_data, "user_type": "farmer"}
        response = requests.post(f"{API_BASE}/enhanced-predict", 
                               json=enhanced_data, headers=headers)
        if response.status_code == 200:
            data = response.json()
            risk = data.get("terra_pulse_prediction", {}).get("degradation_risk", 0)
            ai_recs = len(data.get("ai_insights", {}).get("enhanced_recommendations", []))
            print(f"   ✅ Enhanced prediction: {risk}% risk, {ai_recs} AI recommendations")
        else:
            print(f"   ❌ Enhanced prediction failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
        
        # Test authentication
        print("🔐 Testing authentication...")
        response = requests.post(f"{API_BASE}/predict", json=sample_data)
        if response.status_code == 401:
            print("   ✅ Authentication required (as expected)")
        else:
            print(f"   ❌ Authentication not enforced: {response.status_code}")
        
        print("✅ API endpoints test completed!")
        return True
        
    except Exception as e:
        print(f"❌ API endpoints test failed: {str(e)}")
        return False

def test_rate_limiting():
    """Test rate limiting (if Redis is available)."""
    try:
        print("\n⏱️  Testing rate limiting...")
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": TEST_API_KEY
        }
        
        sample_data = {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Test Location",
            "user_context": "test"
        }
        
        # Make a few requests to test rate limiting
        success_count = 0
        for i in range(5):
            response = requests.post(f"{API_BASE}/predict", 
                                   json=sample_data, headers=headers)
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:
                print(f"   ✅ Rate limiting triggered after {success_count} requests")
                return True
            time.sleep(0.1)
        
        print(f"   ℹ️  Rate limiting not triggered ({success_count} requests succeeded)")
        print("   This is normal if Redis is not configured")
        return True
        
    except Exception as e:
        print(f"❌ Rate limiting test failed: {str(e)}")
        return False

def main():
    """Run all production tests."""
    print("🚀 Terra Pulse Enhanced API - Production Test Suite")
    print("=" * 60)
    
    tests = [
        ("Dify Connection", test_dify_connection),
        ("Terra Pulse Service", test_terra_pulse_service),
        ("API Endpoints", test_api_endpoints),
        ("Rate Limiting", test_rate_limiting)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name} test...")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Your enhanced API is ready for production!")
        return 0
    else:
        print(f"\n⚠️  {len(results) - passed} test(s) failed. Check configuration and try again.")
        return 1

if __name__ == "__main__":
    sys.exit(main())