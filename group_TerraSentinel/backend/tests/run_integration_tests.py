"""
Comprehensive test runner for Terra Pulse-Dify integration tests.
Executes end-to-end, performance, and system resilience tests with reporting.
"""

import pytest
import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any
import subprocess

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class IntegrationTestRunner:
    """Comprehensive test runner for integration tests."""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.end_time = None
        
    def run_all_tests(self, verbose: bool = True, generate_report: bool = True) -> Dict[str, Any]:
        """Run all integration tests and generate comprehensive report."""
        print("=" * 80)
        print("Terra Pulse-Dify Integration Test Suite")
        print("=" * 80)
        
        self.start_time = time.time()
        
        # Define test suites
        test_suites = [
            {
                'name': 'End-to-End Integration Tests',
                'file': 'tests/test_end_to_end_integration.py',
                'description': 'Complete workflow validation and fallback scenarios'
            },
            {
                'name': 'Performance Benchmarks',
                'file': 'tests/test_performance_benchmarks.py',
                'description': 'Performance testing and optimization validation'
            },
            {
                'name': 'System Resilience Tests',
                'file': 'tests/test_system_resilience.py',
                'description': 'Error recovery and monitoring functionality'
            }
        ]
        
        # Run each test suite
        for suite in test_suites:
            print(f"\n{'-' * 60}")
            print(f"Running: {suite['name']}")
            print(f"Description: {suite['description']}")
            print(f"File: {suite['file']}")
            print(f"{'-' * 60}")
            
            result = self._run_test_suite(suite['file'], verbose)
            self.test_results[suite['name']] = {
                'file': suite['file'],
                'description': suite['description'],
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        self.end_time = time.time()
        
        # Generate comprehensive report
        if generate_report:
            report = self._generate_comprehensive_report()
            self._save_report(report)
            return report
        
        return self.test_results
    
    def _run_test_suite(self, test_file: str, verbose: bool = True) -> Dict[str, Any]:
        """Run a specific test suite and capture results."""
        try:
            # Prepare pytest arguments
            pytest_args = [test_file, '--tb=short', '--no-header']
            if verbose:
                pytest_args.extend(['-v', '-s'])
            
            # Add JSON report generation
            json_report_file = f"test_results_{os.path.basename(test_file).replace('.py', '')}.json"
            pytest_args.extend(['--json-report', f'--json-report-file={json_report_file}'])
            
            print(f"Executing: pytest {' '.join(pytest_args)}")
            
            # Run pytest
            start_time = time.time()
            exit_code = pytest.main(pytest_args)
            end_time = time.time()
            
            # Load JSON report if available
            test_details = self._load_json_report(json_report_file)
            
            return {
                'exit_code': exit_code,
                'duration_seconds': end_time - start_time,
                'success': exit_code == 0,
                'details': test_details,
                'json_report_file': json_report_file
            }
            
        except Exception as e:
            return {
                'exit_code': -1,
                'duration_seconds': 0,
                'success': False,
                'error': str(e),
                'details': None
            }
    
    def _load_json_report(self, json_file: str) -> Dict[str, Any]:
        """Load pytest JSON report if available."""
        try:
            if os.path.exists(json_file):
                with open(json_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load JSON report {json_file}: {e}")
        return {}
    
    def _generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        # Calculate overall statistics
        total_suites = len(self.test_results)
        successful_suites = sum(1 for result in self.test_results.values() if result['result']['success'])
        
        # Aggregate test statistics
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        
        for suite_name, suite_data in self.test_results.items():
            details = suite_data['result'].get('details', {})
            summary = details.get('summary', {})
            
            total_tests += summary.get('total', 0)
            passed_tests += summary.get('passed', 0)
            failed_tests += summary.get('failed', 0)
            skipped_tests += summary.get('skipped', 0)
        
        report = {
            'test_run_info': {
                'timestamp': datetime.utcnow().isoformat(),
                'total_duration_seconds': total_duration,
                'total_duration_formatted': f"{total_duration:.2f}s"
            },
            'summary': {
                'total_test_suites': total_suites,
                'successful_suites': successful_suites,
                'failed_suites': total_suites - successful_suites,
                'suite_success_rate': successful_suites / total_suites if total_suites > 0 else 0,
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'skipped_tests': skipped_tests,
                'test_success_rate': passed_tests / total_tests if total_tests > 0 else 0
            },
            'test_suites': self.test_results,
            'recommendations': self._generate_recommendations(),
            'system_validation': self._validate_system_readiness()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Check for failed test suites
        for suite_name, suite_data in self.test_results.items():
            if not suite_data['result']['success']:
                recommendations.append({
                    'category': 'test_failure',
                    'priority': 'high',
                    'message': f"{suite_name} failed - system may not be ready for production",
                    'action': f"Review and fix issues in {suite_data['file']}"
                })
        
        # Check performance test results
        perf_suite = self.test_results.get('Performance Benchmarks', {})
        if perf_suite and perf_suite['result']['success']:
            recommendations.append({
                'category': 'performance',
                'priority': 'medium',
                'message': "Performance tests passed - consider running load tests in staging",
                'action': "Execute performance optimization recommendations"
            })
        
        # Check resilience test results
        resilience_suite = self.test_results.get('System Resilience Tests', {})
        if resilience_suite and resilience_suite['result']['success']:
            recommendations.append({
                'category': 'resilience',
                'priority': 'low',
                'message': "System resilience validated - monitoring and alerting functional",
                'action': "Configure production monitoring thresholds"
            })
        
        # Overall system readiness
        all_passed = all(suite['result']['success'] for suite in self.test_results.values())
        if all_passed:
            recommendations.append({
                'category': 'deployment',
                'priority': 'low',
                'message': "All integration tests passed - system ready for deployment",
                'action': "Proceed with deployment to staging/production environment"
            })
        
        return recommendations
    
    def _validate_system_readiness(self) -> Dict[str, Any]:
        """Validate overall system readiness based on test results."""
        validation = {
            'ready_for_production': True,
            'critical_issues': [],
            'warnings': [],
            'validation_checks': {}
        }
        
        # Check each test suite
        for suite_name, suite_data in self.test_results.items():
            suite_success = suite_data['result']['success']
            validation['validation_checks'][suite_name] = {
                'passed': suite_success,
                'duration': suite_data['result']['duration_seconds']
            }
            
            if not suite_success:
                validation['ready_for_production'] = False
                validation['critical_issues'].append(f"{suite_name} failed")
        
        # Performance validation
        perf_suite = self.test_results.get('Performance Benchmarks', {})
        if perf_suite and perf_suite['result']['duration_seconds'] > 300:  # 5 minutes
            validation['warnings'].append("Performance tests took longer than expected")
        
        # Resilience validation
        resilience_suite = self.test_results.get('System Resilience Tests', {})
        if resilience_suite and not resilience_suite['result']['success']:
            validation['critical_issues'].append("System resilience tests failed - error recovery may be compromised")
        
        return validation
    
    def _save_report(self, report: Dict[str, Any]) -> str:
        """Save comprehensive report to file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"integration_test_report_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            
            print(f"\n{'=' * 80}")
            print("INTEGRATION TEST REPORT SUMMARY")
            print(f"{'=' * 80}")
            print(f"Report saved to: {filename}")
            print(f"Total duration: {report['test_run_info']['total_duration_formatted']}")
            print(f"Test suites: {report['summary']['successful_suites']}/{report['summary']['total_test_suites']} passed")
            print(f"Individual tests: {report['summary']['passed_tests']}/{report['summary']['total_tests']} passed")
            print(f"Overall success rate: {report['summary']['test_success_rate']:.1%}")
            
            if report['system_validation']['ready_for_production']:
                print("✅ System is ready for production deployment")
            else:
                print("❌ System has critical issues - not ready for production")
                for issue in report['system_validation']['critical_issues']:
                    print(f"   - {issue}")
            
            if report['system_validation']['warnings']:
                print("\n⚠️  Warnings:")
                for warning in report['system_validation']['warnings']:
                    print(f"   - {warning}")
            
            print(f"\n📋 Recommendations ({len(report['recommendations'])}):")
            for rec in report['recommendations'][:3]:  # Show top 3
                print(f"   [{rec['priority'].upper()}] {rec['message']}")
            
            print(f"{'=' * 80}")
            
            return filename
            
        except Exception as e:
            print(f"Error saving report: {e}")
            return ""
    
    def run_specific_test_class(self, test_file: str, test_class: str, verbose: bool = True) -> Dict[str, Any]:
        """Run a specific test class."""
        test_path = f"{test_file}::{test_class}"
        return self._run_test_suite(test_path, verbose)
    
    def run_smoke_tests(self) -> Dict[str, Any]:
        """Run a subset of critical tests for smoke testing."""
        print("Running smoke tests for critical functionality...")
        
        # Define critical test classes
        smoke_tests = [
            ('tests/test_end_to_end_integration.py', 'TestCompleteWorkflowSuccess'),
            ('tests/test_system_resilience.py', 'TestServiceFailureRecovery'),
        ]
        
        smoke_results = {}
        
        for test_file, test_class in smoke_tests:
            print(f"\nRunning smoke test: {test_class}")
            result = self.run_specific_test_class(test_file, test_class, verbose=False)
            smoke_results[f"{test_class}"] = result
        
        # Generate smoke test summary
        all_passed = all(result['success'] for result in smoke_results.values())
        
        summary = {
            'smoke_tests_passed': all_passed,
            'results': smoke_results,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if all_passed:
            print("✅ All smoke tests passed - basic functionality verified")
        else:
            print("❌ Smoke tests failed - critical issues detected")
        
        return summary


def main():
    """Main entry point for integration test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Terra Pulse-Dify integration tests')
    parser.add_argument('--smoke', action='store_true', help='Run smoke tests only')
    parser.add_argument('--no-report', action='store_true', help='Skip report generation')
    parser.add_argument('--quiet', action='store_true', help='Reduce output verbosity')
    parser.add_argument('--suite', type=str, help='Run specific test suite file')
    parser.add_argument('--class', type=str, help='Run specific test class (requires --suite)')
    
    args = parser.parse_args()
    
    runner = IntegrationTestRunner()
    
    try:
        if args.smoke:
            # Run smoke tests
            result = runner.run_smoke_tests()
            return 0 if result['smoke_tests_passed'] else 1
        
        elif args.suite:
            # Run specific suite or class
            if args.class:
                result = runner.run_specific_test_class(args.suite, args.class, not args.quiet)
            else:
                result = runner._run_test_suite(args.suite, not args.quiet)
            
            return 0 if result['success'] else 1
        
        else:
            # Run all tests
            report = runner.run_all_tests(
                verbose=not args.quiet,
                generate_report=not args.no_report
            )
            
            # Return appropriate exit code
            return 0 if report['system_validation']['ready_for_production'] else 1
    
    except KeyboardInterrupt:
        print("\n\nTest execution interrupted by user")
        return 130
    
    except Exception as e:
        print(f"\nError running tests: {e}")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)