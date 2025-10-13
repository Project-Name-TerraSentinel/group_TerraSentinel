#!/usr/bin/env python3
"""
Deployment Validation Script for Terra Pulse-Dify Integration API

This script validates that a deployment is working correctly by running
comprehensive checks on the API endpoints, services, and configuration.
"""

import os
import sys
import time
import json
import requests
import argparse
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ValidationResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"

@dataclass
class TestResult:
    name: str
    result: ValidationResult
    message: str
    details: Optional[Dict[str, Any]] = None
    duration: Optional[float] = None

class DeploymentValidator:
    """Validates Terra Pulse API deployment."""
    
    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-API-Key': api_key
        })
        self.results: List[TestResult] = []
    
    def log_result(self, name: str, result: ValidationResult, message: str, 
                   details: Optional[Dict[str, Any]] = None, duration: Optional[float] = None):
        """Log a test result."""
        test_result = TestResult(name, result, message, details, duration)
        self.results.append(test_result)
        
        # Print result immediately
        status_icon = {
            ValidationResult.PASS: "✅",
            ValidationResult.FAIL: "❌", 
            ValidationResult.WARN: "⚠️",
            ValidationResult.SKIP: "⏭️"
        }
        
        duration_str = f" ({duration:.2f}s)" if duration else ""
        print(f"{status_icon[result]} {name}: {message}{duration_str}")
        
        if details and result in [ValidationResult.FAIL, ValidationResult.WARN]:
            for key, value in details.items():
                print(f"   {key}: {value}")
    
    def make_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """Make HTTP request with error handling."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method, url, 
                timeout=self.timeout,
                **kwargs
            )
            return response
        except requests.exceptions.RequestException as e:
            return None
    
    def validate_service_availability(self) -> bool:
        """Validate that the service is available and responding."""
        start_time = time.time()
        
        try:
            response = self.make_request('GET', '/health/system')
            duration = time.time() - start_time
            
            if response is None:
                self.log_result(
                    "Service Availability", 
                    ValidationResult.FAIL,
                    "Service is not responding",
                    {"url": self.base_url},
                    duration
                )
                return False
            
            if response.status_code in [200, 503]:
                self.log_result(
                    "Service Availability",
                    ValidationResult.PASS,
                    f"Service responding (HTTP {response.status_code})",
                    duration=duration
                )
                return True
            else:
                self.log_result(
                    "Service Availability",
                    ValidationResult.FAIL,
                    f"Unexpected status code: {response.status_code}",
                    {"response": response.text[:200]},
                    duration
                )
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result(
                "Service Availability",
                ValidationResult.FAIL,
                f"Connection error: {str(e)}",
                duration=duration
            )
            return False
    
    def validate_api_documentation(self):
        """Validate API documentation endpoint."""
        start_time = time.time()
        
        # Remove API key for documentation endpoint
        headers = {'Content-Type': 'application/json'}
        response = requests.get(f"{self.base_url}/", headers=headers, timeout=self.timeout)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            try:
                data = response.json()
                required_fields = ['service', 'version', 'endpoints', 'authentication']
                missing_fields = [f for f in required_fields if f not in data]
                
                if not missing_fields:
                    self.log_result(
                        "API Documentation",
                        ValidationResult.PASS,
                        "Documentation available and complete",
                        duration=duration
                    )
                else:
                    self.log_result(
                        "API Documentation",
                        ValidationResult.WARN,
                        "Documentation missing some fields",
                        {"missing_fields": missing_fields},
                        duration
                    )
            except json.JSONDecodeError:
                self.log_result(
                    "API Documentation",
                    ValidationResult.FAIL,
                    "Documentation endpoint returned invalid JSON",
                    duration=duration
                )
        else:
            self.log_result(
                "API Documentation",
                ValidationResult.FAIL,
                f"Documentation endpoint failed: HTTP {response.status_code}",
                duration=duration
            )
    
    def validate_health_endpoints(self):
        """Validate all health check endpoints."""
        health_endpoints = [
            ('/health/system', 'System Health'),
            ('/health/terra-pulse', 'Terra Pulse Health'),
            ('/health/dify', 'Dify Health')
        ]
        
        for endpoint, name in health_endpoints:
            start_time = time.time()
            response = self.make_request('GET', endpoint)
            duration = time.time() - start_time
            
            if response is None:
                self.log_result(
                    name,
                    ValidationResult.FAIL,
                    "Health endpoint not responding",
                    duration=duration
                )
                continue
            
            if response.status_code in [200, 503]:
                try:
                    data = response.json()
                    status = data.get('status', 'unknown')
                    
                    if status == 'healthy':
                        result = ValidationResult.PASS
                        message = "Service healthy"
                    elif status == 'unhealthy':
                        result = ValidationResult.WARN
                        message = "Service unhealthy but responding"
                    else:
                        result = ValidationResult.WARN
                        message = f"Service status: {status}"
                    
                    self.log_result(name, result, message, duration=duration)
                    
                except json.JSONDecodeError:
                    self.log_result(
                        name,
                        ValidationResult.FAIL,
                        "Health endpoint returned invalid JSON",
                        duration=duration
                    )
            else:
                self.log_result(
                    name,
                    ValidationResult.FAIL,
                    f"Health endpoint failed: HTTP {response.status_code}",
                    duration=duration
                )
    
    def validate_metrics_endpoint(self):
        """Validate metrics endpoint."""
        start_time = time.time()
        response = self.make_request('GET', '/metrics')
        duration = time.time() - start_time
        
        if response is None:
            self.log_result(
                "Metrics Endpoint",
                ValidationResult.FAIL,
                "Metrics endpoint not responding",
                duration=duration
            )
            return
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'text/plain' in content_type:
                metrics_text = response.text
                
                # Check for expected metrics
                expected_metrics = [
                    'terra_pulse_service_health',
                    'dify_service_health',
                    'cache_available'
                ]
                
                missing_metrics = [m for m in expected_metrics if m not in metrics_text]
                
                if not missing_metrics:
                    self.log_result(
                        "Metrics Endpoint",
                        ValidationResult.PASS,
                        "Metrics endpoint working with expected metrics",
                        duration=duration
                    )
                else:
                    self.log_result(
                        "Metrics Endpoint",
                        ValidationResult.WARN,
                        "Some expected metrics missing",
                        {"missing_metrics": missing_metrics},
                        duration
                    )
            else:
                self.log_result(
                    "Metrics Endpoint",
                    ValidationResult.FAIL,
                    f"Metrics endpoint wrong content type: {content_type}",
                    duration=duration
                )
        else:
            self.log_result(
                "Metrics Endpoint",
                ValidationResult.FAIL,
                f"Metrics endpoint failed: HTTP {response.status_code}",
                duration=duration
            )
    
    def validate_authentication(self):
        """Validate API key authentication."""
        sample_data = {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Test Location",
            "user_context": "validation_test"
        }
        
        # Test with valid API key
        start_time = time.time()
        response = self.make_request('POST', '/predict', json=sample_data)
        duration = time.time() - start_time
        
        if response and response.status_code == 200:
            self.log_result(
                "Valid API Key",
                ValidationResult.PASS,
                "Authentication working with valid API key",
                duration=duration
            )
        else:
            status = response.status_code if response else "No response"
            self.log_result(
                "Valid API Key",
                ValidationResult.FAIL,
                f"Authentication failed with valid key: {status}",
                duration=duration
            )
        
        # Test with invalid API key
        start_time = time.time()
        invalid_session = requests.Session()
        invalid_session.headers.update({
            'Content-Type': 'application/json',
            'X-API-Key': 'invalid-key-12345'
        })
        
        try:
            invalid_response = invalid_session.post(
                f"{self.base_url}/predict",
                json=sample_data,
                timeout=self.timeout
            )
            duration = time.time() - start_time
            
            if invalid_response.status_code == 401:
                self.log_result(
                    "Invalid API Key Rejection",
                    ValidationResult.PASS,
                    "Invalid API key properly rejected",
                    duration=duration
                )
            else:
                self.log_result(
                    "Invalid API Key Rejection",
                    ValidationResult.FAIL,
                    f"Invalid API key not rejected: HTTP {invalid_response.status_code}",
                    duration=duration
                )
        except requests.exceptions.RequestException:
            duration = time.time() - start_time
            self.log_result(
                "Invalid API Key Rejection",
                ValidationResult.FAIL,
                "Could not test invalid API key rejection",
                duration=duration
            )
    
    def validate_prediction_endpoints(self):
        """Validate prediction endpoints functionality."""
        sample_data = {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Validation Test Location",
            "user_context": "deployment_validation"
        }
        
        # Test basic prediction
        start_time = time.time()
        response = self.make_request('POST', '/predict', json=sample_data)
        duration = time.time() - start_time
        
        if response and response.status_code == 200:
            try:
                data = response.json()
                if 'ml_output' in data and 'degradation_risk' in data['ml_output']:
                    self.log_result(
                        "Basic Prediction",
                        ValidationResult.PASS,
                        f"Basic prediction working (risk: {data['ml_output']['degradation_risk']}%)",
                        duration=duration
                    )
                else:
                    self.log_result(
                        "Basic Prediction",
                        ValidationResult.FAIL,
                        "Basic prediction response missing expected fields",
                        {"response_keys": list(data.keys())},
                        duration
                    )
            except json.JSONDecodeError:
                self.log_result(
                    "Basic Prediction",
                    ValidationResult.FAIL,
                    "Basic prediction returned invalid JSON",
                    duration=duration
                )
        else:
            status = response.status_code if response else "No response"
            self.log_result(
                "Basic Prediction",
                ValidationResult.FAIL,
                f"Basic prediction failed: {status}",
                duration=duration
            )
        
        # Test enhanced prediction
        enhanced_data = {**sample_data, 'user_type': 'farmer'}
        start_time = time.time()
        response = self.make_request('POST', '/enhanced-predict', json=enhanced_data)
        duration = time.time() - start_time
        
        if response and response.status_code == 200:
            try:
                data = response.json()
                required_sections = ['terra_pulse_prediction', 'ai_insights', 'formatted_response', 'metadata']
                missing_sections = [s for s in required_sections if s not in data]
                
                if not missing_sections:
                    dify_success = data.get('metadata', {}).get('dify_success', False)
                    if dify_success:
                        result = ValidationResult.PASS
                        message = "Enhanced prediction working with AI insights"
                    else:
                        result = ValidationResult.WARN
                        message = "Enhanced prediction working with fallback (Dify unavailable)"
                    
                    self.log_result("Enhanced Prediction", result, message, duration=duration)
                else:
                    self.log_result(
                        "Enhanced Prediction",
                        ValidationResult.FAIL,
                        "Enhanced prediction response missing sections",
                        {"missing_sections": missing_sections},
                        duration
                    )
            except json.JSONDecodeError:
                self.log_result(
                    "Enhanced Prediction",
                    ValidationResult.FAIL,
                    "Enhanced prediction returned invalid JSON",
                    duration=duration
                )
        else:
            status = response.status_code if response else "No response"
            self.log_result(
                "Enhanced Prediction",
                ValidationResult.FAIL,
                f"Enhanced prediction failed: {status}",
                duration=duration
            )
    
    def validate_error_handling(self):
        """Validate error handling for invalid requests."""
        # Test missing required fields
        start_time = time.time()
        invalid_data = {"location": "Test"}
        response = self.make_request('POST', '/predict', json=invalid_data)
        duration = time.time() - start_time
        
        if response and response.status_code == 400:
            try:
                data = response.json()
                if 'error' in data:
                    self.log_result(
                        "Error Handling",
                        ValidationResult.PASS,
                        f"Invalid request properly rejected: {data['error']}",
                        duration=duration
                    )
                else:
                    self.log_result(
                        "Error Handling",
                        ValidationResult.WARN,
                        "Invalid request rejected but error format unexpected",
                        duration=duration
                    )
            except json.JSONDecodeError:
                self.log_result(
                    "Error Handling",
                    ValidationResult.WARN,
                    "Invalid request rejected but response not JSON",
                    duration=duration
                )
        else:
            status = response.status_code if response else "No response"
            self.log_result(
                "Error Handling",
                ValidationResult.FAIL,
                f"Invalid request not properly rejected: {status}",
                duration=duration
            )
    
    def validate_performance(self):
        """Validate basic performance requirements."""
        sample_data = {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Performance Test",
            "user_context": "performance_validation"
        }
        
        # Test basic prediction performance
        start_time = time.time()
        response = self.make_request('POST', '/predict', json=sample_data)
        duration = time.time() - start_time
        
        if response and response.status_code == 200:
            if duration < 5.0:
                self.log_result(
                    "Basic Prediction Performance",
                    ValidationResult.PASS,
                    f"Basic prediction within 5s requirement",
                    duration=duration
                )
            else:
                self.log_result(
                    "Basic Prediction Performance",
                    ValidationResult.WARN,
                    f"Basic prediction slower than 5s requirement",
                    duration=duration
                )
        else:
            self.log_result(
                "Basic Prediction Performance",
                ValidationResult.SKIP,
                "Cannot test performance - prediction failed",
                duration=duration
            )
        
        # Test enhanced prediction performance
        enhanced_data = {**sample_data, 'user_type': 'farmer'}
        start_time = time.time()
        response = self.make_request('POST', '/enhanced-predict', json=enhanced_data)
        duration = time.time() - start_time
        
        if response and response.status_code == 200:
            if duration < 10.0:
                self.log_result(
                    "Enhanced Prediction Performance",
                    ValidationResult.PASS,
                    f"Enhanced prediction within 10s requirement",
                    duration=duration
                )
            else:
                self.log_result(
                    "Enhanced Prediction Performance",
                    ValidationResult.WARN,
                    f"Enhanced prediction slower than 10s requirement",
                    duration=duration
                )
        else:
            self.log_result(
                "Enhanced Prediction Performance",
                ValidationResult.SKIP,
                "Cannot test performance - enhanced prediction failed",
                duration=duration
            )
    
    def run_all_validations(self) -> bool:
        """Run all validation tests."""
        print(f"🚀 Starting deployment validation for {self.base_url}")
        print("=" * 60)
        
        # Check service availability first
        if not self.validate_service_availability():
            print("\n❌ Service not available - skipping remaining tests")
            return False
        
        # Run all validation tests
        validation_methods = [
            self.validate_api_documentation,
            self.validate_health_endpoints,
            self.validate_metrics_endpoint,
            self.validate_authentication,
            self.validate_prediction_endpoints,
            self.validate_error_handling,
            self.validate_performance
        ]
        
        for method in validation_methods:
            try:
                method()
            except Exception as e:
                self.log_result(
                    method.__name__.replace('validate_', '').replace('_', ' ').title(),
                    ValidationResult.FAIL,
                    f"Validation test failed with exception: {str(e)}"
                )
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        
        pass_count = sum(1 for r in self.results if r.result == ValidationResult.PASS)
        fail_count = sum(1 for r in self.results if r.result == ValidationResult.FAIL)
        warn_count = sum(1 for r in self.results if r.result == ValidationResult.WARN)
        skip_count = sum(1 for r in self.results if r.result == ValidationResult.SKIP)
        total_count = len(self.results)
        
        print(f"✅ Passed: {pass_count}")
        print(f"❌ Failed: {fail_count}")
        print(f"⚠️  Warnings: {warn_count}")
        print(f"⏭️  Skipped: {skip_count}")
        print(f"📈 Total: {total_count}")
        
        success_rate = (pass_count / total_count) * 100 if total_count > 0 else 0
        print(f"🎯 Success Rate: {success_rate:.1f}%")
        
        # Overall result
        if fail_count == 0:
            if warn_count == 0:
                print("\n🎉 DEPLOYMENT VALIDATION: EXCELLENT")
                print("All tests passed! Deployment is ready for production.")
            else:
                print("\n✅ DEPLOYMENT VALIDATION: GOOD")
                print("All critical tests passed. Some warnings to review.")
            return True
        else:
            print("\n❌ DEPLOYMENT VALIDATION: FAILED")
            print("Critical issues found. Deployment needs attention.")
            
            # Show failed tests
            failed_tests = [r for r in self.results if r.result == ValidationResult.FAIL]
            print("\nFailed Tests:")
            for test in failed_tests:
                print(f"  - {test.name}: {test.message}")
            
            return False


def main():
    """Main function for deployment validation."""
    parser = argparse.ArgumentParser(description='Validate Terra Pulse API deployment')
    parser.add_argument('--url', default='http://localhost:5000', 
                       help='Base URL of the API (default: http://localhost:5000)')
    parser.add_argument('--api-key', default='test-validation-key-12345',
                       help='API key for testing (default: test-validation-key-12345)')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Request timeout in seconds (default: 30)')
    parser.add_argument('--json', action='store_true',
                       help='Output results in JSON format')
    
    args = parser.parse_args()
    
    # Create validator and run tests
    validator = DeploymentValidator(args.url, args.api_key, args.timeout)
    success = validator.run_all_validations()
    
    # Output JSON results if requested
    if args.json:
        results_data = {
            'success': success,
            'summary': {
                'total': len(validator.results),
                'passed': sum(1 for r in validator.results if r.result == ValidationResult.PASS),
                'failed': sum(1 for r in validator.results if r.result == ValidationResult.FAIL),
                'warnings': sum(1 for r in validator.results if r.result == ValidationResult.WARN),
                'skipped': sum(1 for r in validator.results if r.result == ValidationResult.SKIP)
            },
            'tests': [
                {
                    'name': r.name,
                    'result': r.result.value,
                    'message': r.message,
                    'details': r.details,
                    'duration': r.duration
                }
                for r in validator.results
            ]
        }
        print(json.dumps(results_data, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()