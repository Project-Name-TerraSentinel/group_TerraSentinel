"""
Performance testing and benchmarking for Terra Pulse-Dify integration.
Tests response times, throughput, and resource usage under various loads.
"""

import pytest
import json
import time
import threading
import statistics
import psutil
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
from flask import Flask
import requests

# Import the app and services
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app, terra_pulse_service, dify_service, redis_client
from backend.services.terra_pulse_service import PredictionOutput
from backend.config.settings import get_config


class PerformanceMetrics:
    """Container for performance metrics."""
    
    def __init__(self):
        self.response_times = []
        self.success_count = 0
        self.error_count = 0
        self.start_time = None
        self.end_time = None
        self.memory_usage = []
        self.cpu_usage = []
    
    def add_response_time(self, response_time_ms):
        """Add a response time measurement."""
        self.response_times.append(response_time_ms)
    
    def add_success(self):
        """Record a successful request."""
        self.success_count += 1
    
    def add_error(self):
        """Record a failed request."""
        self.error_count += 1
    
    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        gc.collect()  # Clean up before monitoring
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self.end_time = time.time()
    
    def record_system_metrics(self):
        """Record current system metrics."""
        process = psutil.Process()
        self.memory_usage.append(process.memory_info().rss / 1024 / 1024)  # MB
        self.cpu_usage.append(process.cpu_percent())
    
    def get_summary(self):
        """Get performance summary statistics."""
        if not self.response_times:
            return {"error": "No response times recorded"}
        
        total_requests = self.success_count + self.error_count
        duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        return {
            "total_requests": total_requests,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "success_rate": self.success_count / total_requests if total_requests > 0 else 0,
            "duration_seconds": duration,
            "requests_per_second": total_requests / duration if duration > 0 else 0,
            "response_times": {
                "min_ms": min(self.response_times),
                "max_ms": max(self.response_times),
                "mean_ms": statistics.mean(self.response_times),
                "median_ms": statistics.median(self.response_times),
                "p95_ms": self._percentile(self.response_times, 95),
                "p99_ms": self._percentile(self.response_times, 99)
            },
            "memory_usage": {
                "min_mb": min(self.memory_usage) if self.memory_usage else 0,
                "max_mb": max(self.memory_usage) if self.memory_usage else 0,
                "mean_mb": statistics.mean(self.memory_usage) if self.memory_usage else 0
            },
            "cpu_usage": {
                "mean_percent": statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
                "max_percent": max(self.cpu_usage) if self.cpu_usage else 0
            }
        }
    
    def _percentile(self, data, percentile):
        """Calculate percentile of data."""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def config(self):
        """Get application configuration."""
        return get_config()
    
    @pytest.fixture
    def valid_request(self):
        """Valid prediction request for benchmarking."""
        return {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Performance Test Location",
            "user_context": "benchmark_user",
            "user_type": "farmer"
        }
    
    @pytest.fixture
    def api_key(self):
        """Valid API key."""
        return "benchmark-api-key-12345"
    
    @pytest.fixture
    def mock_terra_pulse_fast(self):
        """Fast mock Terra Pulse response."""
        return PredictionOutput(
            degradation_risk=65,
            risk_factors=["moderate_ndvi_drop"],
            recommended_action_key="increase_soil_cover",
            confidence=0.80,
            location="Performance Test Location",
            user_context="benchmark_user",
            raw_prediction=0.65,
            processing_time_ms=50.0  # Fast response
        )
    
    @pytest.fixture
    def mock_dify_fast(self):
        """Fast mock Dify response."""
        return {
            'status': 'success',
            'workflow_run_id': 'benchmark-123',
            'enhanced_recommendations': [
                'Apply soil conservation measures',
                'Monitor vegetation health'
            ],
            'risk_assessment': 'Moderate risk detected',
            'timeline': 'Action within 2 weeks',
            'cost_estimate': 'Medium cost',
            'success_probability': 0.75,
            'processing_time': 100.0  # Fast response
        }


class TestSingleRequestPerformance(TestPerformanceBenchmarks):
    """Test performance of individual requests."""
    
    def test_enhanced_predict_baseline_performance(self, client, valid_request, api_key,
                                                 mock_terra_pulse_fast, mock_dify_fast):
        """Test baseline performance of enhanced predict endpoint."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_fast), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_fast):
            
            # Warm up
            for _ in range(3):
                client.post('/enhanced-predict',
                           data=json.dumps(valid_request),
                           content_type='application/json',
                           headers={'X-API-Key': api_key})
            
            # Measure performance
            response_times = []
            for _ in range(10):
                start_time = time.time()
                response = client.post('/enhanced-predict',
                                     data=json.dumps(valid_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                end_time = time.time()
                
                assert response.status_code == 200
                response_times.append((end_time - start_time) * 1000)
            
            # Analyze performance
            mean_time = statistics.mean(response_times)
            p95_time = sorted(response_times)[int(len(response_times) * 0.95)]
            
            print(f"Baseline Performance:")
            print(f"  Mean response time: {mean_time:.2f}ms")
            print(f"  P95 response time: {p95_time:.2f}ms")
            print(f"  Min response time: {min(response_times):.2f}ms")
            print(f"  Max response time: {max(response_times):.2f}ms")
            
            # Performance assertions
            assert mean_time < 500, f"Mean response time {mean_time:.2f}ms exceeds 500ms threshold"
            assert p95_time < 1000, f"P95 response time {p95_time:.2f}ms exceeds 1000ms threshold"
    
    def test_terra_pulse_only_performance(self, client, api_key):
        """Test performance of original Terra Pulse endpoint."""
        terra_request = {
            "NDVI_mean_early": 0.45,
            "NDVI_median_early": 0.43,
            "NDVI_std_early": 0.12,
            "NDVI_mean_late": 0.38,
            "NDVI_median_late": 0.36,
            "NDVI_std_late": 0.15,
            "NDVI_delta_mean": -0.07,
            "location": "Performance Test",
            "user_context": "benchmark"
        }
        
        response_times = []
        for _ in range(10):
            start_time = time.time()
            response = client.post('/predict',
                                 data=json.dumps(terra_request),
                                 content_type='application/json',
                                 headers={'X-API-Key': api_key})
            end_time = time.time()
            
            # May fail if ONNX model not available in test environment
            if response.status_code == 200:
                response_times.append((end_time - start_time) * 1000)
        
        if response_times:
            mean_time = statistics.mean(response_times)
            print(f"Terra Pulse Only Performance: {mean_time:.2f}ms mean")
            assert mean_time < 200, f"Terra Pulse response time {mean_time:.2f}ms exceeds 200ms"
    
    def test_memory_usage_single_request(self, client, valid_request, api_key,
                                       mock_terra_pulse_fast, mock_dify_fast):
        """Test memory usage for single requests."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_fast), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_fast):
            
            process = psutil.Process()
            
            # Baseline memory
            gc.collect()
            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Make requests and measure memory
            memory_measurements = []
            for i in range(20):
                response = client.post('/enhanced-predict',
                                     data=json.dumps(valid_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                assert response.status_code == 200
                
                if i % 5 == 0:  # Measure every 5 requests
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_measurements.append(current_memory - baseline_memory)
            
            # Check for memory leaks
            memory_growth = max(memory_measurements) - min(memory_measurements)
            print(f"Memory usage: baseline={baseline_memory:.1f}MB, growth={memory_growth:.1f}MB")
            
            # Should not grow more than 50MB for 20 requests
            assert memory_growth < 50, f"Memory growth {memory_growth:.1f}MB indicates potential leak"


class TestLoadTesting(TestPerformanceBenchmarks):
    """Load testing with concurrent requests."""
    
    def test_concurrent_requests_performance(self, client, valid_request, api_key,
                                           mock_terra_pulse_fast, mock_dify_fast):
        """Test performance under concurrent load."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_fast), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_fast):
            
            metrics = PerformanceMetrics()
            
            def make_request():
                """Make a single request and record metrics."""
                try:
                    start_time = time.time()
                    response = client.post('/enhanced-predict',
                                         data=json.dumps(valid_request),
                                         content_type='application/json',
                                         headers={'X-API-Key': api_key})
                    end_time = time.time()
                    
                    response_time_ms = (end_time - start_time) * 1000
                    metrics.add_response_time(response_time_ms)
                    
                    if response.status_code == 200:
                        metrics.add_success()
                    else:
                        metrics.add_error()
                        
                except Exception as e:
                    metrics.add_error()
                    print(f"Request failed: {e}")
            
            # Test with different concurrency levels
            concurrency_levels = [1, 5, 10, 20]
            results = {}
            
            for concurrency in concurrency_levels:
                print(f"\nTesting with {concurrency} concurrent requests...")
                
                metrics = PerformanceMetrics()
                metrics.start_monitoring()
                
                # Monitor system resources
                def monitor_resources():
                    for _ in range(10):  # Monitor for ~5 seconds
                        metrics.record_system_metrics()
                        time.sleep(0.5)
                
                monitor_thread = threading.Thread(target=monitor_resources)
                monitor_thread.start()
                
                # Execute concurrent requests
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = [executor.submit(make_request) for _ in range(50)]  # 50 requests total
                    
                    for future in as_completed(futures):
                        future.result()  # Wait for completion
                
                metrics.stop_monitoring()
                monitor_thread.join()
                
                summary = metrics.get_summary()
                results[concurrency] = summary
                
                print(f"  Success rate: {summary['success_rate']:.2%}")
                print(f"  Mean response time: {summary['response_times']['mean_ms']:.2f}ms")
                print(f"  P95 response time: {summary['response_times']['p95_ms']:.2f}ms")
                print(f"  Requests/second: {summary['requests_per_second']:.2f}")
                
                # Performance assertions
                assert summary['success_rate'] >= 0.95, f"Success rate {summary['success_rate']:.2%} below 95%"
                assert summary['response_times']['p95_ms'] < 2000, f"P95 response time too high: {summary['response_times']['p95_ms']:.2f}ms"
            
            # Analyze scalability
            print(f"\nScalability Analysis:")
            for concurrency in concurrency_levels:
                result = results[concurrency]
                print(f"  {concurrency} threads: {result['requests_per_second']:.2f} req/s, "
                      f"{result['response_times']['mean_ms']:.2f}ms mean")
    
    def test_sustained_load_performance(self, client, valid_request, api_key,
                                      mock_terra_pulse_fast, mock_dify_fast):
        """Test performance under sustained load."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_fast), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_fast):
            
            metrics = PerformanceMetrics()
            metrics.start_monitoring()
            
            # Run sustained load for 30 seconds
            end_time = time.time() + 30
            request_count = 0
            
            while time.time() < end_time:
                start_time = time.time()
                response = client.post('/enhanced-predict',
                                     data=json.dumps(valid_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                response_time = (time.time() - start_time) * 1000
                
                metrics.add_response_time(response_time)
                if response.status_code == 200:
                    metrics.add_success()
                else:
                    metrics.add_error()
                
                request_count += 1
                
                # Record system metrics every 10 requests
                if request_count % 10 == 0:
                    metrics.record_system_metrics()
                
                # Small delay to prevent overwhelming
                time.sleep(0.01)
            
            metrics.stop_monitoring()
            summary = metrics.get_summary()
            
            print(f"Sustained Load Results:")
            print(f"  Total requests: {summary['total_requests']}")
            print(f"  Success rate: {summary['success_rate']:.2%}")
            print(f"  Average RPS: {summary['requests_per_second']:.2f}")
            print(f"  Mean response time: {summary['response_times']['mean_ms']:.2f}ms")
            print(f"  Memory usage: {summary['memory_usage']['mean_mb']:.1f}MB avg")
            
            # Performance assertions for sustained load
            assert summary['success_rate'] >= 0.98, "Success rate degraded under sustained load"
            assert summary['response_times']['mean_ms'] < 1000, "Response time degraded under sustained load"


class TestCachePerformanceOptimization(TestPerformanceBenchmarks):
    """Test caching performance and optimization."""
    
    def test_cache_hit_performance(self, client, valid_request, api_key,
                                 mock_terra_pulse_fast, mock_dify_fast):
        """Test performance improvement with cache hits."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_fast), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_fast):
            
            # First request (cache miss)
            start_time = time.time()
            response1 = client.post('/enhanced-predict',
                                  data=json.dumps(valid_request),
                                  content_type='application/json',
                                  headers={'X-API-Key': api_key})
            miss_time = (time.time() - start_time) * 1000
            
            assert response1.status_code == 200
            
            # Second identical request (should be cache hit if caching is working)
            start_time = time.time()
            response2 = client.post('/enhanced-predict',
                                  data=json.dumps(valid_request),
                                  content_type='application/json',
                                  headers={'X-API-Key': api_key})
            hit_time = (time.time() - start_time) * 1000
            
            assert response2.status_code == 200
            
            print(f"Cache Performance:")
            print(f"  Cache miss time: {miss_time:.2f}ms")
            print(f"  Cache hit time: {hit_time:.2f}ms")
            print(f"  Improvement: {((miss_time - hit_time) / miss_time * 100):.1f}%")
            
            # Cache hit should be faster (if caching is implemented)
            # Note: This test may not show improvement if caching is not fully implemented
            if hit_time < miss_time * 0.8:  # 20% improvement
                print("  Cache optimization detected!")
    
    def test_cache_strategy_effectiveness(self, client, api_key,
                                        mock_terra_pulse_fast, mock_dify_fast):
        """Test effectiveness of different caching strategies."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_fast), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_fast):
            
            # Test different request patterns
            base_request = {
                "NDVI_mean_early": 0.45,
                "NDVI_median_early": 0.43,
                "NDVI_std_early": 0.12,
                "NDVI_mean_late": 0.38,
                "NDVI_median_late": 0.36,
                "NDVI_std_late": 0.15,
                "NDVI_delta_mean": -0.07,
                "location": "Cache Test Location",
                "user_context": "cache_test",
                "user_type": "farmer"
            }
            
            # Pattern 1: Identical requests (should benefit from caching)
            identical_times = []
            for _ in range(5):
                start_time = time.time()
                response = client.post('/enhanced-predict',
                                     data=json.dumps(base_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                identical_times.append((time.time() - start_time) * 1000)
                assert response.status_code == 200
            
            # Pattern 2: Slightly different requests (cache misses)
            different_times = []
            for i in range(5):
                modified_request = base_request.copy()
                modified_request['NDVI_mean_early'] = 0.45 + (i * 0.01)  # Slight variation
                
                start_time = time.time()
                response = client.post('/enhanced-predict',
                                     data=json.dumps(modified_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                different_times.append((time.time() - start_time) * 1000)
                assert response.status_code == 200
            
            print(f"Cache Strategy Analysis:")
            print(f"  Identical requests mean time: {statistics.mean(identical_times):.2f}ms")
            print(f"  Different requests mean time: {statistics.mean(different_times):.2f}ms")
            
            # If caching is working, identical requests should show improvement over time
            if len(identical_times) >= 3:
                first_request = identical_times[0]
                later_requests = statistics.mean(identical_times[1:])
                improvement = (first_request - later_requests) / first_request * 100
                print(f"  Cache improvement: {improvement:.1f}%")


class TestResourceOptimization(TestPerformanceBenchmarks):
    """Test resource usage optimization."""
    
    def test_memory_efficiency(self, client, valid_request, api_key,
                             mock_terra_pulse_fast, mock_dify_fast):
        """Test memory efficiency under load."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_fast), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_fast):
            
            process = psutil.Process()
            
            # Baseline measurement
            gc.collect()
            baseline_memory = process.memory_info().rss / 1024 / 1024
            
            # Process many requests
            memory_samples = []
            for i in range(100):
                response = client.post('/enhanced-predict',
                                     data=json.dumps(valid_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                assert response.status_code == 200
                
                # Sample memory every 10 requests
                if i % 10 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(current_memory - baseline_memory)
            
            # Force garbage collection and final measurement
            gc.collect()
            final_memory = process.memory_info().rss / 1024 / 1024
            
            print(f"Memory Efficiency Analysis:")
            print(f"  Baseline: {baseline_memory:.1f}MB")
            print(f"  Peak growth: {max(memory_samples):.1f}MB")
            print(f"  Final growth: {final_memory - baseline_memory:.1f}MB")
            print(f"  Memory samples: {[f'{m:.1f}' for m in memory_samples]}")
            
            # Memory should not grow excessively
            peak_growth = max(memory_samples)
            final_growth = final_memory - baseline_memory
            
            assert peak_growth < 100, f"Peak memory growth {peak_growth:.1f}MB too high"
            assert final_growth < 50, f"Final memory growth {final_growth:.1f}MB indicates leak"
    
    def test_cpu_efficiency(self, client, valid_request, api_key,
                          mock_terra_pulse_fast, mock_dify_fast):
        """Test CPU efficiency under load."""
        with patch.object(terra_pulse_service, 'predict', return_value=mock_terra_pulse_fast), \
             patch.object(dify_service, 'execute_workflow', return_value=mock_dify_fast):
            
            process = psutil.Process()
            cpu_samples = []
            
            # Monitor CPU during request processing
            def monitor_cpu():
                for _ in range(20):  # Monitor for ~10 seconds
                    cpu_samples.append(process.cpu_percent())
                    time.sleep(0.5)
            
            monitor_thread = threading.Thread(target=monitor_cpu)
            monitor_thread.start()
            
            # Generate load
            for _ in range(50):
                response = client.post('/enhanced-predict',
                                     data=json.dumps(valid_request),
                                     content_type='application/json',
                                     headers={'X-API-Key': api_key})
                assert response.status_code == 200
                time.sleep(0.1)  # Small delay
            
            monitor_thread.join()
            
            if cpu_samples:
                avg_cpu = statistics.mean(cpu_samples)
                max_cpu = max(cpu_samples)
                
                print(f"CPU Efficiency Analysis:")
                print(f"  Average CPU: {avg_cpu:.1f}%")
                print(f"  Peak CPU: {max_cpu:.1f}%")
                
                # CPU usage should be reasonable
                assert avg_cpu < 80, f"Average CPU usage {avg_cpu:.1f}% too high"
                assert max_cpu < 95, f"Peak CPU usage {max_cpu:.1f}% too high"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])  # -s to see print output