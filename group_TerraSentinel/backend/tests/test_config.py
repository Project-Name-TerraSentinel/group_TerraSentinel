"""
Test Configuration for Terra Pulse-Dify Integration API

This module provides configuration settings for different test environments
and test data for deployment and integration testing.
"""

import os
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class TestEnvironment:
    """Configuration for a test environment."""
    name: str
    base_url: str
    api_key: str
    timeout: int
    expected_services: List[str]
    performance_thresholds: Dict[str, float]
    features_enabled: Dict[str, bool]

# Test environments configuration
TEST_ENVIRONMENTS = {
    'local': TestEnvironment(
        name='Local Development',
        base_url='http://localhost:5000',
        api_key='test-local-key-12345',
        timeout=30,
        expected_services=['terra_pulse', 'dify', 'cache'],
        performance_thresholds={
            'basic_prediction_ms': 5000,
            'enhanced_prediction_ms': 10000,
            'health_check_ms': 1000
        },
        features_enabled={
            'basic_predictions': True,
            'enhanced_predictions': True,
            'caching': True,
            'rate_limiting': True,
            'authentication': True
        }
    ),
    
    'docker': TestEnvironment(
        name='Docker Compose',
        base_url='http://localhost:5000',
        api_key='test-docker-key-12345',
        timeout=45,  # Docker may be slower
        expected_services=['terra_pulse', 'dify', 'cache'],
        performance_thresholds={
            'basic_prediction_ms': 7000,  # Allow more time in Docker
            'enhanced_prediction_ms': 15000,
            'health_check_ms': 2000
        },
        features_enabled={
            'basic_predictions': True,
            'enhanced_predictions': True,
            'caching': True,
            'rate_limiting': True,
            'authentication': True
        }
    ),
    
    'staging': TestEnvironment(
        name='Staging Environment',
        base_url=os.getenv('STAGING_API_URL', 'https://terra-pulse-staging.onrender.com'),
        api_key=os.getenv('STAGING_API_KEY', 'staging-test-key'),
        timeout=60,  # Network latency
        expected_services=['terra_pulse', 'dify', 'cache'],
        performance_thresholds={
            'basic_prediction_ms': 8000,
            'enhanced_prediction_ms': 20000,
            'health_check_ms': 3000
        },
        features_enabled={
            'basic_predictions': True,
            'enhanced_predictions': True,
            'caching': True,
            'rate_limiting': True,
            'authentication': True
        }
    ),
    
    'production': TestEnvironment(
        name='Production Environment',
        base_url=os.getenv('PROD_API_URL', 'https://terra-pulse-api.onrender.com'),
        api_key=os.getenv('PROD_API_KEY', 'production-test-key'),
        timeout=60,
        expected_services=['terra_pulse', 'dify', 'cache'],
        performance_thresholds={
            'basic_prediction_ms': 5000,
            'enhanced_prediction_ms': 15000,
            'health_check_ms': 2000
        },
        features_enabled={
            'basic_predictions': True,
            'enhanced_predictions': True,
            'caching': True,
            'rate_limiting': True,
            'authentication': True
        }
    )
}

# Test data sets
TEST_DATA_SETS = {
    'valid_basic': {
        "NDVI_mean_early": 0.45,
        "NDVI_median_early": 0.43,
        "NDVI_std_early": 0.12,
        "NDVI_mean_late": 0.38,
        "NDVI_median_late": 0.36,
        "NDVI_std_late": 0.15,
        "NDVI_delta_mean": -0.07,
        "location": "Baringo County, Kenya",
        "user_context": "test_user"
    },
    
    'valid_enhanced_farmer': {
        "NDVI_mean_early": 0.52,
        "NDVI_median_early": 0.50,
        "NDVI_std_early": 0.08,
        "NDVI_mean_late": 0.41,
        "NDVI_median_late": 0.39,
        "NDVI_std_late": 0.11,
        "NDVI_delta_mean": -0.11,
        "location": "Turkana County, Kenya",
        "user_context": "smallholder_farmer",
        "user_type": "farmer"
    },
    
    'valid_enhanced_official': {
        "NDVI_mean_early": 0.38,
        "NDVI_median_early": 0.36,
        "NDVI_std_early": 0.15,
        "NDVI_mean_late": 0.25,
        "NDVI_median_late": 0.23,
        "NDVI_std_late": 0.18,
        "NDVI_delta_mean": -0.13,
        "location": "Marsabit County, Kenya",
        "user_context": "government_official",
        "user_type": "official"
    },
    
    'high_risk_scenario': {
        "NDVI_mean_early": 0.25,
        "NDVI_median_early": 0.23,
        "NDVI_std_early": 0.20,
        "NDVI_mean_late": 0.15,
        "NDVI_median_late": 0.13,
        "NDVI_std_late": 0.22,
        "NDVI_delta_mean": -0.10,
        "location": "Arid Test Region",
        "user_context": "high_risk_test",
        "user_type": "farmer"
    },
    
    'low_risk_scenario': {
        "NDVI_mean_early": 0.75,
        "NDVI_median_early": 0.73,
        "NDVI_std_early": 0.05,
        "NDVI_mean_late": 0.72,
        "NDVI_median_late": 0.70,
        "NDVI_std_late": 0.06,
        "NDVI_delta_mean": -0.03,
        "location": "Fertile Test Region",
        "user_context": "low_risk_test",
        "user_type": "official"
    },
    
    'edge_case_values': {
        "NDVI_mean_early": 0.99,
        "NDVI_median_early": 1.0,
        "NDVI_std_early": 0.01,
        "NDVI_mean_late": -0.99,
        "NDVI_median_late": -1.0,
        "NDVI_std_late": 0.01,
        "NDVI_delta_mean": -1.99,
        "location": "Edge Case Test",
        "user_context": "edge_case_test",
        "user_type": "farmer"
    }
}

# Invalid test data for error handling tests
INVALID_TEST_DATA = {
    'missing_required_fields': {
        "location": "Test Location",
        "user_context": "test"
    },
    
    'invalid_ndvi_range': {
        "NDVI_mean_early": 2.0,  # Invalid: > 1.0
        "NDVI_median_early": 0.43,
        "NDVI_std_early": 0.12,
        "NDVI_mean_late": 0.38,
        "NDVI_median_late": 0.36,
        "NDVI_std_late": 0.15,
        "NDVI_delta_mean": -0.07,
        "location": "Test Location",
        "user_context": "test"
    },
    
    'invalid_data_types': {
        "NDVI_mean_early": "not_a_number",
        "NDVI_median_early": 0.43,
        "NDVI_std_early": 0.12,
        "NDVI_mean_late": 0.38,
        "NDVI_median_late": 0.36,
        "NDVI_std_late": 0.15,
        "NDVI_delta_mean": -0.07,
        "location": "Test Location",
        "user_context": "test"
    },
    
    'invalid_user_type': {
        "NDVI_mean_early": 0.45,
        "NDVI_median_early": 0.43,
        "NDVI_std_early": 0.12,
        "NDVI_mean_late": 0.38,
        "NDVI_median_late": 0.36,
        "NDVI_std_late": 0.15,
        "NDVI_delta_mean": -0.07,
        "location": "Test Location",
        "user_context": "test",
        "user_type": "invalid_type"
    },
    
    'malicious_input': {
        "NDVI_mean_early": 0.45,
        "NDVI_median_early": 0.43,
        "NDVI_std_early": 0.12,
        "NDVI_mean_late": 0.38,
        "NDVI_median_late": 0.36,
        "NDVI_std_late": 0.15,
        "NDVI_delta_mean": -0.07,
        "location": "<script>alert('xss')</script>",
        "user_context": "'; DROP TABLE users; --",
        "user_type": "farmer"
    }
}

# Expected response structures for validation
EXPECTED_RESPONSE_STRUCTURES = {
    'basic_prediction': {
        'required_fields': ['ml_output'],
        'ml_output_fields': [
            'location', 'degradation_risk', 'risk_factors', 
            'recommended_action_key', 'confidence', 'user_context'
        ]
    },
    
    'enhanced_prediction': {
        'required_fields': [
            'terra_pulse_prediction', 'ai_insights', 
            'formatted_response', 'metadata'
        ],
        'ai_insights_fields': [
            'enhanced_recommendations', 'risk_assessment', 
            'timeline', 'cost_estimate', 'success_probability'
        ],
        'formatted_response_fields': ['farmer_message'],
        'metadata_fields': [
            'processing_time_ms', 'timestamp', 'dify_success'
        ]
    },
    
    'health_response': {
        'required_fields': ['status', 'timestamp'],
        'optional_fields': ['message', 'response_time_ms']
    },
    
    'system_health_response': {
        'required_fields': [
            'system', 'overall_status', 'services', 
            'capabilities', 'timestamp'
        ],
        'services_fields': ['terra_pulse', 'dify', 'cache'],
        'capabilities_fields': [
            'basic_predictions', 'enhanced_predictions', 'caching'
        ]
    },
    
    'error_response': {
        'required_fields': ['error', 'message', 'timestamp'],
        'optional_fields': ['details', 'error_id']
    }
}

# Performance benchmarks
PERFORMANCE_BENCHMARKS = {
    'response_times': {
        'health_check': {'target': 500, 'max': 2000},  # ms
        'basic_prediction': {'target': 2000, 'max': 5000},  # ms
        'enhanced_prediction': {'target': 5000, 'max': 15000},  # ms
        'metrics': {'target': 1000, 'max': 3000}  # ms
    },
    
    'throughput': {
        'concurrent_requests': 5,
        'success_rate_threshold': 0.8,
        'max_error_rate': 0.2
    },
    
    'resource_usage': {
        'max_memory_growth_mb': 100,  # Max memory growth during test
        'max_response_size_kb': 50    # Max response size
    }
}

# Security test configurations
SECURITY_TEST_CONFIG = {
    'rate_limiting': {
        'requests_per_minute': 60,
        'test_requests': 65,
        'expected_status': 429
    },
    
    'input_validation': {
        'max_string_length': 1000,
        'forbidden_patterns': [
            '<script>', 'javascript:', 'DROP TABLE', 
            'SELECT * FROM', 'UNION SELECT'
        ]
    },
    
    'authentication': {
        'invalid_keys': [
            '', 'invalid', '12345', 'test', 'null', 'undefined'
        ],
        'expected_status': 401
    }
}

def get_test_environment(env_name: str = None) -> TestEnvironment:
    """Get test environment configuration."""
    if env_name is None:
        env_name = os.getenv('TEST_ENVIRONMENT', 'local')
    
    if env_name not in TEST_ENVIRONMENTS:
        raise ValueError(f"Unknown test environment: {env_name}")
    
    return TEST_ENVIRONMENTS[env_name]

def get_test_data(data_name: str) -> Dict[str, Any]:
    """Get test data by name."""
    if data_name in TEST_DATA_SETS:
        return TEST_DATA_SETS[data_name].copy()
    elif data_name in INVALID_TEST_DATA:
        return INVALID_TEST_DATA[data_name].copy()
    else:
        raise ValueError(f"Unknown test data: {data_name}")

def validate_response_structure(response_data: Dict[str, Any], 
                              structure_name: str) -> List[str]:
    """Validate response structure and return list of missing fields."""
    if structure_name not in EXPECTED_RESPONSE_STRUCTURES:
        raise ValueError(f"Unknown response structure: {structure_name}")
    
    structure = EXPECTED_RESPONSE_STRUCTURES[structure_name]
    missing_fields = []
    
    # Check required fields
    for field in structure['required_fields']:
        if field not in response_data:
            missing_fields.append(field)
    
    # Check nested structures if they exist
    if structure_name == 'enhanced_prediction' and 'ai_insights' in response_data:
        for field in structure['ai_insights_fields']:
            if field not in response_data['ai_insights']:
                missing_fields.append(f"ai_insights.{field}")
    
    return missing_fields

def get_performance_threshold(metric_name: str, environment: str = 'local') -> float:
    """Get performance threshold for a metric."""
    env_config = get_test_environment(environment)
    return env_config.performance_thresholds.get(metric_name, float('inf'))

def is_feature_enabled(feature_name: str, environment: str = 'local') -> bool:
    """Check if a feature is enabled in the test environment."""
    env_config = get_test_environment(environment)
    return env_config.features_enabled.get(feature_name, False)