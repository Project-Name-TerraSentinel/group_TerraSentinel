#!/usr/bin/env python3
"""
Deployment Test Runner for Terra Pulse-Dify Integration API

This script orchestrates the execution of all deployment and integration tests,
providing comprehensive validation of the deployed system.
"""

import os
import sys
import time
import json
import argparse
import subprocess
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from validate_deployment import DeploymentValidator
from tests.test_config import get_test_environment, TEST_ENVIRONMENTS

class DeploymentTestRunner:
    """Orchestrates deployment testing."""
    
    def __init__(self, environment: str = 'local', verbose: bool = False):
        self.environment = environment
        self.verbose = verbose
        self.test_config = get_test_environment(environment)
        self.results = {}
        
    def log(self, message: str, level: str = 'INFO'):
        """Log message with timestamp."""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        prefix = {
            'INFO': '📋',
            'SUCCESS': '✅',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'DEBUG': '🔍'
        }.get(level, 'ℹ️')
        
        print(f"[{timestamp}] {prefix} {message}")
        
        if self.verbose and level == 'DEBUG':
            print(f"    Environment: {self.environment}")
            print(f"    Base URL: {self.test_config.base_url}")
    
    def check_prerequisites(self) -> bool:
        """Check if prerequisites for testing are met."""
        self.log("Checking test prerequisites...")
        
        # Check Python dependencies
        required_packages = ['requests', 'pytest', 'docker']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            self.log(f"Missing required packages: {missing_packages}", 'ERROR')
            self.log("Install with: pip install " + " ".join(missing_packages), 'INFO')
            return False
        
        # Check if service is reachable
        try:
            import requests
            response = requests.get(
                f"{self.test_config.base_url}/health/system",
                timeout=10
            )
            if response.status_code in [200, 503]:
                self.log("Service is reachable", 'SUCCESS')
                return True
            else:
                self.log(f"Service returned unexpected status: {response.status_code}", 'WARNING')
                return True  # Continue anyway
        except Exception as e:
            self.log(f"Service not reachable: {e}", 'ERROR')
            return False
    
    def run_deployment_validation(self) -> bool:
        """Run deployment validation tests."""
        self.log("Running deployment validation...")
        
        try:
            validator = DeploymentValidator(
                self.test_config.base_url,
                self.test_config.api_key,
                self.test_config.timeout
            )
            
            success = validator.run_all_validations()
            
            # Store results
            self.results['deployment_validation'] = {
                'success': success,
                'tests': [
                    {
                        'name': r.name,
                        'result': r.result.value,
                        'message': r.message,
                        'duration': r.duration
                    }
                    for r in validator.results
                ]
            }
            
            if success:
                self.log("Deployment validation passed", 'SUCCESS')
            else:
                self.log("Deployment validation failed", 'ERROR')
            
            return success
            
        except Exception as e:
            self.log(f"Deployment validation error: {e}", 'ERROR')
            self.results['deployment_validation'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def run_pytest_tests(self) -> bool:
        """Run pytest integration tests."""
        self.log("Running pytest integration tests...")
        
        try:
            # Set environment variables for tests
            test_env = os.environ.copy()
            test_env.update({
                'TEST_API_URL': self.test_config.base_url,
                'TEST_API_KEY': self.test_config.api_key,
                'TEST_ENVIRONMENT': self.environment,
                'PYTEST_RUNNING': '1'
            })
            
            # Run pytest
            pytest_args = [
                sys.executable, '-m', 'pytest',
                'tests/test_deployment_integration.py',
                '-v',
                '--tb=short',
                f'--timeout={self.test_config.timeout}',
                '--disable-warnings'
            ]
            
            if self.verbose:
                pytest_args.append('-s')
            
            result = subprocess.run(
                pytest_args,
                env=test_env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for all tests
            )
            
            # Store results
            self.results['pytest_tests'] = {
                'success': result.returncode == 0,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
            if result.returncode == 0:
                self.log("Pytest integration tests passed", 'SUCCESS')
                if self.verbose:
                    print(result.stdout)
            else:
                self.log("Pytest integration tests failed", 'ERROR')
                if self.verbose:
                    print("STDOUT:", result.stdout)
                    print("STDERR:", result.stderr)
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            self.log("Pytest tests timed out", 'ERROR')
            self.results['pytest_tests'] = {
                'success': False,
                'error': 'timeout'
            }
            return False
        except Exception as e:
            self.log(f"Pytest execution error: {e}", 'ERROR')
            self.results['pytest_tests'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def run_performance_tests(self) -> bool:
        """Run performance tests."""
        self.log("Running performance tests...")
        
        try:
            import requests
            import threading
            import queue
            
            # Test concurrent requests
            results_queue = queue.Queue()
            num_threads = 5
            
            def make_concurrent_request():
                try:
                    start_time = time.time()
                    response = requests.post(
                        f"{self.test_config.base_url}/predict",
                        json={
                            "NDVI_mean_early": 0.45,
                            "NDVI_median_early": 0.43,
                            "NDVI_std_early": 0.12,
                            "NDVI_mean_late": 0.38,
                            "NDVI_median_late": 0.36,
                            "NDVI_std_late": 0.15,
                            "NDVI_delta_mean": -0.07,
                            "location": "Performance Test",
                            "user_context": "performance_test"
                        },
                        headers={
                            'Content-Type': 'application/json',
                            'X-API-Key': self.test_config.api_key
                        },
                        timeout=self.test_config.timeout
                    )
                    duration = time.time() - start_time
                    results_queue.put(('success', response.status_code, duration))
                except Exception as e:
                    results_queue.put(('error', str(e), 0))
            
            # Start concurrent requests
            threads = []
            start_time = time.time()
            
            for _ in range(num_threads):
                thread = threading.Thread(target=make_concurrent_request)
                thread.start()
                threads.append(thread)
            
            # Wait for completion
            for thread in threads:
                thread.join(timeout=60)
            
            total_time = time.time() - start_time
            
            # Analyze results
            success_count = 0
            error_count = 0
            response_times = []
            
            while not results_queue.empty():
                result_type, result_value, duration = results_queue.get()
                if result_type == 'success' and result_value == 200:
                    success_count += 1
                    response_times.append(duration)
                else:
                    error_count += 1
            
            success_rate = success_count / num_threads if num_threads > 0 else 0
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # Store results
            self.results['performance_tests'] = {
                'success': success_rate >= 0.8,
                'concurrent_requests': num_threads,
                'success_count': success_count,
                'error_count': error_count,
                'success_rate': success_rate,
                'avg_response_time': avg_response_time,
                'total_time': total_time
            }
            
            if success_rate >= 0.8:
                self.log(f"Performance tests passed (success rate: {success_rate:.2f})", 'SUCCESS')
            else:
                self.log(f"Performance tests failed (success rate: {success_rate:.2f})", 'ERROR')
            
            return success_rate >= 0.8
            
        except Exception as e:
            self.log(f"Performance test error: {e}", 'ERROR')
            self.results['performance_tests'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def run_security_tests(self) -> bool:
        """Run basic security tests."""
        self.log("Running security tests...")
        
        try:
            import requests
            
            security_results = []
            
            # Test 1: Invalid API key rejection
            try:
                response = requests.post(
                    f"{self.test_config.base_url}/predict",
                    json={"location": "test"},
                    headers={
                        'Content-Type': 'application/json',
                        'X-API-Key': 'invalid-key'
                    },
                    timeout=10
                )
                
                if response.status_code == 401:
                    security_results.append(('api_key_validation', True, 'Invalid API key properly rejected'))
                else:
                    security_results.append(('api_key_validation', False, f'Invalid API key not rejected: {response.status_code}'))
            except Exception as e:
                security_results.append(('api_key_validation', False, f'API key test error: {e}'))
            
            # Test 2: Input validation
            try:
                response = requests.post(
                    f"{self.test_config.base_url}/predict",
                    json={
                        "location": "<script>alert('xss')</script>",
                        "user_context": "'; DROP TABLE users; --"
                    },
                    headers={
                        'Content-Type': 'application/json',
                        'X-API-Key': self.test_config.api_key
                    },
                    timeout=10
                )
                
                if response.status_code == 400:
                    security_results.append(('input_validation', True, 'Malicious input properly rejected'))
                elif response.status_code == 200:
                    # Check if input was sanitized
                    data = response.json()
                    location = data.get('ml_output', {}).get('location', '')
                    if '<script>' not in location:
                        security_results.append(('input_validation', True, 'Malicious input sanitized'))
                    else:
                        security_results.append(('input_validation', False, 'Malicious input not sanitized'))
                else:
                    security_results.append(('input_validation', False, f'Unexpected response: {response.status_code}'))
            except Exception as e:
                security_results.append(('input_validation', False, f'Input validation test error: {e}'))
            
            # Analyze results
            passed_tests = sum(1 for _, success, _ in security_results if success)
            total_tests = len(security_results)
            success = passed_tests == total_tests
            
            self.results['security_tests'] = {
                'success': success,
                'passed': passed_tests,
                'total': total_tests,
                'tests': [
                    {'name': name, 'success': success, 'message': message}
                    for name, success, message in security_results
                ]
            }
            
            if success:
                self.log(f"Security tests passed ({passed_tests}/{total_tests})", 'SUCCESS')
            else:
                self.log(f"Security tests failed ({passed_tests}/{total_tests})", 'ERROR')
            
            return success
            
        except Exception as e:
            self.log(f"Security test error: {e}", 'ERROR')
            self.results['security_tests'] = {
                'success': False,
                'error': str(e)
            }
            return False
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        self.log("Generating test report...")
        
        # Calculate overall success
        test_categories = ['deployment_validation', 'pytest_tests', 'performance_tests', 'security_tests']
        successful_categories = sum(
            1 for category in test_categories 
            if self.results.get(category, {}).get('success', False)
        )
        
        overall_success = successful_categories == len(test_categories)
        
        report = {
            'environment': self.environment,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
            'base_url': self.test_config.base_url,
            'overall_success': overall_success,
            'summary': {
                'total_categories': len(test_categories),
                'successful_categories': successful_categories,
                'success_rate': successful_categories / len(test_categories)
            },
            'results': self.results
        }
        
        return report
    
    def run_all_tests(self) -> bool:
        """Run all deployment tests."""
        self.log(f"Starting deployment tests for environment: {self.environment}")
        self.log(f"Target URL: {self.test_config.base_url}")
        
        # Check prerequisites
        if not self.check_prerequisites():
            self.log("Prerequisites not met - aborting tests", 'ERROR')
            return False
        
        # Run test categories
        test_methods = [
            ('Deployment Validation', self.run_deployment_validation),
            ('Integration Tests', self.run_pytest_tests),
            ('Performance Tests', self.run_performance_tests),
            ('Security Tests', self.run_security_tests)
        ]
        
        results = []
        for test_name, test_method in test_methods:
            self.log(f"Starting {test_name}...")
            try:
                success = test_method()
                results.append(success)
                if success:
                    self.log(f"{test_name} completed successfully", 'SUCCESS')
                else:
                    self.log(f"{test_name} failed", 'ERROR')
            except Exception as e:
                self.log(f"{test_name} error: {e}", 'ERROR')
                results.append(False)
        
        # Generate final report
        overall_success = all(results)
        
        self.log("=" * 60)
        if overall_success:
            self.log("🎉 ALL DEPLOYMENT TESTS PASSED!", 'SUCCESS')
            self.log("Deployment is ready for production use.", 'SUCCESS')
        else:
            self.log("❌ DEPLOYMENT TESTS FAILED", 'ERROR')
            self.log("Please review failed tests and fix issues before deployment.", 'ERROR')
        
        return overall_success


def main():
    """Main function for deployment test runner."""
    parser = argparse.ArgumentParser(description='Run Terra Pulse API deployment tests')
    parser.add_argument('--environment', '-e', 
                       choices=list(TEST_ENVIRONMENTS.keys()),
                       default='local',
                       help='Test environment (default: local)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--report', '-r', 
                       help='Save detailed report to JSON file')
    parser.add_argument('--list-environments', action='store_true',
                       help='List available test environments')
    
    args = parser.parse_args()
    
    # List environments if requested
    if args.list_environments:
        print("Available test environments:")
        for name, env in TEST_ENVIRONMENTS.items():
            print(f"  {name}: {env.name} ({env.base_url})")
        return
    
    # Run tests
    runner = DeploymentTestRunner(args.environment, args.verbose)
    success = runner.run_all_tests()
    
    # Generate and save report if requested
    if args.report:
        report = runner.generate_report()
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Detailed report saved to: {args.report}")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()