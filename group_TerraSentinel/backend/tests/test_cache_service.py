"""
Unit tests for cache service.
Tests cache hit/miss scenarios, TTL behavior, fallback mechanisms, and error handling.
"""

import pytest
import json
import hashlib
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Any, Dict

from backend.services.cache_service import (
    CacheService,
    get_cache_service,
    close_cache_service
)
from backend.config.settings import AppConfig
import redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError


class TestCacheService:
    """Test cases for CacheService."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration for testing."""
        config = Mock(spec=AppConfig)
        config.redis_url = "redis://localhost:6379/0"
        config.cache_ttl = 300  # 5 minutes
        return config
    
    @pytest.fixture
    def sample_prediction_input(self):
        """Create sample prediction input for testing."""
        return {
            "NDVI_mean_early": 0.5,
            "NDVI_median_early": 0.48,
            "NDVI_std_early": 0.1,
            "NDVI_mean_late": 0.45,
            "NDVI_median_late": 0.43,
            "NDVI_std_late": 0.12,
            "NDVI_delta_mean": -0.05,
            "location": "Test Location",
            "user_context": "farmer"
        }
    
    @pytest.fixture
    def sample_prediction_result(self):
        """Create sample prediction result for testing."""
        return {
            "degradation_risk": 75,
            "risk_factors": ["bare_soil_increase", "low_ndvi"],
            "recommended_action_key": "mulch_crop_residue",
            "confidence": 0.85,
            "location": "Test Location",
            "user_context": "farmer"
        }
    
    @pytest.fixture
    def sample_dify_input(self):
        """Create sample Dify input for testing."""
        return {
            "degradation_risk": 75,
            "risk_factors": ["bare_soil_increase", "low_ndvi"],
            "location": "Test Location",
            "user_context": "farmer",
            "confidence": 0.85,
            "recommended_action_key": "mulch_crop_residue"
        }
    
    @pytest.fixture
    def sample_dify_result(self):
        """Create sample Dify result for testing."""
        return {
            "enhanced_recommendations": [
                "Apply crop residue mulch within 2 weeks",
                "Consider drought-resistant maize varieties"
            ],
            "risk_assessment": "High degradation risk due to recent drought conditions",
            "timeline": "Immediate action required within 14 days",
            "cost_estimate": "Low cost - use existing crop residue",
            "success_probability": 0.78
        }
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_cache_service_initialization_success(self, mock_pool, mock_redis, mock_config):
        """Test successful cache service initialization."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        cache_service = CacheService(mock_config)
        
        assert cache_service._is_available is True
        assert cache_service._redis_client is not None
        mock_pool.assert_called_once()
        mock_redis_instance.ping.assert_called_once()
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_cache_service_initialization_connection_failure(self, mock_pool, mock_redis, mock_config):
        """Test cache service initialization when Redis connection fails."""
        mock_pool.side_effect = ConnectionError("Connection failed")
        
        cache_service = CacheService(mock_config)
        
        assert cache_service._is_available is False
        assert cache_service._redis_client is None
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_cache_service_initialization_ping_failure(self, mock_pool, mock_redis, mock_config):
        """Test cache service initialization when ping fails."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.side_effect = RedisError("Ping failed")
        
        cache_service = CacheService(mock_config)
        
        assert cache_service._is_available is False
    
    def test_generate_cache_key_consistency(self, mock_config):
        """Test that cache key generation is consistent for same data."""
        with patch('services.cache_service.redis.Redis'), \
             patch('services.cache_service.ConnectionPool.from_url'):
            
            cache_service = CacheService(mock_config)
            
            data = {"key1": "value1", "key2": "value2"}
            key1 = cache_service._generate_cache_key("test_prefix", data)
            key2 = cache_service._generate_cache_key("test_prefix", data)
            
            assert key1 == key2
            assert key1.startswith("test_prefix:")
    
    def test_generate_cache_key_different_data(self, mock_config):
        """Test that different data generates different cache keys."""
        with patch('services.cache_service.redis.Redis'), \
             patch('services.cache_service.ConnectionPool.from_url'):
            
            cache_service = CacheService(mock_config)
            
            data1 = {"key1": "value1", "key2": "value2"}
            data2 = {"key1": "value1", "key2": "different_value"}
            
            key1 = cache_service._generate_cache_key("test_prefix", data1)
            key2 = cache_service._generate_cache_key("test_prefix", data2)
            
            assert key1 != key2
    
    def test_serialize_deserialize_data(self, mock_config):
        """Test data serialization and deserialization."""
        with patch('services.cache_service.redis.Redis'), \
             patch('services.cache_service.ConnectionPool.from_url'):
            
            cache_service = CacheService(mock_config)
            
            original_data = {
                "string": "test",
                "number": 42,
                "float": 3.14,
                "list": [1, 2, 3],
                "dict": {"nested": "value"}
            }
            
            serialized = cache_service._serialize_data(original_data)
            deserialized = cache_service._deserialize_data(serialized)
            
            assert deserialized == original_data
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_is_available_when_redis_available(self, mock_pool, mock_redis, mock_config):
        """Test is_available returns True when Redis is available."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        cache_service = CacheService(mock_config)
        
        assert cache_service.is_available() is True
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_is_available_when_redis_unavailable(self, mock_pool, mock_redis, mock_config):
        """Test is_available returns False when Redis is unavailable."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        # First ping succeeds (for initialization), second ping fails
        mock_redis_instance.ping.side_effect = [True, RedisError("Connection lost")]
        
        cache_service = CacheService(mock_config)
        # Initially available after successful initialization
        assert cache_service._is_available is True
        
        # Now ping fails, should detect unavailability
        assert cache_service.is_available() is False
        assert cache_service._is_available is False  # Should update internal state
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_get_cache_hit(self, mock_pool, mock_redis, mock_config):
        """Test successful cache get (cache hit)."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        test_data = {"test": "data"}
        serialized_data = json.dumps(test_data)
        mock_redis_instance.get.return_value = serialized_data
        
        cache_service = CacheService(mock_config)
        result = cache_service.get("test_key")
        
        assert result == test_data
        mock_redis_instance.get.assert_called_once_with("test_key")
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_get_cache_miss(self, mock_pool, mock_redis, mock_config):
        """Test cache get when key doesn't exist (cache miss)."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.get.return_value = None
        
        cache_service = CacheService(mock_config)
        result = cache_service.get("nonexistent_key")
        
        assert result is None
        mock_redis_instance.get.assert_called_once_with("nonexistent_key")
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_get_redis_error(self, mock_pool, mock_redis, mock_config):
        """Test cache get when Redis throws an error."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.get.side_effect = RedisError("Redis error")
        
        cache_service = CacheService(mock_config)
        result = cache_service.get("test_key")
        
        assert result is None
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_get_when_unavailable(self, mock_pool, mock_redis, mock_config):
        """Test cache get when Redis is unavailable."""
        cache_service = CacheService(mock_config)
        cache_service._is_available = False
        cache_service._redis_client = None
        
        result = cache_service.get("test_key")
        
        assert result is None
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_set_success(self, mock_pool, mock_redis, mock_config):
        """Test successful cache set."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.setex.return_value = True
        
        cache_service = CacheService(mock_config)
        test_data = {"test": "data"}
        
        result = cache_service.set("test_key", test_data, 600)
        
        assert result is True
        mock_redis_instance.setex.assert_called_once()
        args = mock_redis_instance.setex.call_args[0]
        assert args[0] == "test_key"
        assert args[1] == 600  # TTL
        assert json.loads(args[2]) == test_data
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_set_with_default_ttl(self, mock_pool, mock_redis, mock_config):
        """Test cache set with default TTL from config."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.setex.return_value = True
        
        cache_service = CacheService(mock_config)
        test_data = {"test": "data"}
        
        result = cache_service.set("test_key", test_data)
        
        assert result is True
        args = mock_redis_instance.setex.call_args[0]
        assert args[1] == 300  # Default TTL from config
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_set_redis_error(self, mock_pool, mock_redis, mock_config):
        """Test cache set when Redis throws an error."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.setex.side_effect = RedisError("Redis error")
        
        cache_service = CacheService(mock_config)
        result = cache_service.set("test_key", {"test": "data"})
        
        assert result is False
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_set_when_unavailable(self, mock_pool, mock_redis, mock_config):
        """Test cache set when Redis is unavailable."""
        cache_service = CacheService(mock_config)
        cache_service._is_available = False
        cache_service._redis_client = None
        
        result = cache_service.set("test_key", {"test": "data"})
        
        assert result is False
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_delete_success(self, mock_pool, mock_redis, mock_config):
        """Test successful cache delete."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.delete.return_value = 1
        
        cache_service = CacheService(mock_config)
        result = cache_service.delete("test_key")
        
        assert result is True
        mock_redis_instance.delete.assert_called_once_with("test_key")
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_delete_key_not_found(self, mock_pool, mock_redis, mock_config):
        """Test cache delete when key doesn't exist."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.delete.return_value = 0
        
        cache_service = CacheService(mock_config)
        result = cache_service.delete("nonexistent_key")
        
        assert result is False
    
    def test_get_prediction_cache_key_consistency(self, mock_config, sample_prediction_input):
        """Test that prediction cache key generation is consistent."""
        with patch('services.cache_service.redis.Redis'), \
             patch('services.cache_service.ConnectionPool.from_url'):
            
            cache_service = CacheService(mock_config)
            
            key1 = cache_service.get_prediction_cache_key(sample_prediction_input)
            key2 = cache_service.get_prediction_cache_key(sample_prediction_input)
            
            assert key1 == key2
            assert key1.startswith("terra_pulse:prediction:")
    
    def test_get_prediction_cache_key_different_inputs(self, mock_config, sample_prediction_input):
        """Test that different prediction inputs generate different cache keys."""
        with patch('services.cache_service.redis.Redis'), \
             patch('services.cache_service.ConnectionPool.from_url'):
            
            cache_service = CacheService(mock_config)
            
            input2 = sample_prediction_input.copy()
            input2["NDVI_mean_early"] = 0.6  # Different value
            
            key1 = cache_service.get_prediction_cache_key(sample_prediction_input)
            key2 = cache_service.get_prediction_cache_key(input2)
            
            assert key1 != key2
    
    def test_get_dify_result_cache_key_consistency(self, mock_config, sample_dify_input):
        """Test that Dify result cache key generation is consistent."""
        with patch('services.cache_service.redis.Redis'), \
             patch('services.cache_service.ConnectionPool.from_url'):
            
            cache_service = CacheService(mock_config)
            
            key1 = cache_service.get_dify_result_cache_key(sample_dify_input)
            key2 = cache_service.get_dify_result_cache_key(sample_dify_input)
            
            assert key1 == key2
            assert key1.startswith("terra_pulse:dify_result:")
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_cache_prediction_success(self, mock_pool, mock_redis, mock_config, 
                                    sample_prediction_input, sample_prediction_result):
        """Test successful prediction caching."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.setex.return_value = True
        
        cache_service = CacheService(mock_config)
        
        with patch('services.cache_service.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value.isoformat.return_value = "2024-01-01T00:00:00"
            
            result = cache_service.cache_prediction(sample_prediction_input, sample_prediction_result)
            
            assert result is True
            mock_redis_instance.setex.assert_called_once()
            
            # Verify cached data structure
            args = mock_redis_instance.setex.call_args[0]
            cached_data = json.loads(args[2])
            assert cached_data["result"] == sample_prediction_result
            assert cached_data["cached_at"] == "2024-01-01T00:00:00"
            assert "input_hash" in cached_data
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_get_cached_prediction_hit(self, mock_pool, mock_redis, mock_config, 
                                     sample_prediction_input, sample_prediction_result):
        """Test getting cached prediction (cache hit)."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        cached_data = {
            "result": sample_prediction_result,
            "cached_at": "2024-01-01T00:00:00",
            "input_hash": "test_hash"
        }
        mock_redis_instance.get.return_value = json.dumps(cached_data)
        
        cache_service = CacheService(mock_config)
        result = cache_service.get_cached_prediction(sample_prediction_input)
        
        assert result == sample_prediction_result
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_get_cached_prediction_miss(self, mock_pool, mock_redis, mock_config, sample_prediction_input):
        """Test getting cached prediction (cache miss)."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.get.return_value = None
        
        cache_service = CacheService(mock_config)
        result = cache_service.get_cached_prediction(sample_prediction_input)
        
        assert result is None
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_cache_dify_result_success(self, mock_pool, mock_redis, mock_config, 
                                     sample_dify_input, sample_dify_result):
        """Test successful Dify result caching."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.setex.return_value = True
        
        cache_service = CacheService(mock_config)
        
        with patch('services.cache_service.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value.isoformat.return_value = "2024-01-01T00:00:00"
            
            result = cache_service.cache_dify_result(sample_dify_input, sample_dify_result)
            
            assert result is True
            mock_redis_instance.setex.assert_called_once()
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_get_cached_dify_result_hit(self, mock_pool, mock_redis, mock_config, 
                                      sample_dify_input, sample_dify_result):
        """Test getting cached Dify result (cache hit)."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        cached_data = {
            "result": sample_dify_result,
            "cached_at": "2024-01-01T00:00:00",
            "input_hash": "test_hash"
        }
        mock_redis_instance.get.return_value = json.dumps(cached_data)
        
        cache_service = CacheService(mock_config)
        result = cache_service.get_cached_dify_result(sample_dify_input)
        
        assert result == sample_dify_result
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_invalidate_prediction_cache_success(self, mock_pool, mock_redis, mock_config):
        """Test successful prediction cache invalidation."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.keys.return_value = ["key1", "key2", "key3"]
        mock_redis_instance.delete.return_value = 3
        
        cache_service = CacheService(mock_config)
        result = cache_service.invalidate_prediction_cache()
        
        assert result == 3
        mock_redis_instance.keys.assert_called_once_with("terra_pulse:prediction:*")
        mock_redis_instance.delete.assert_called_once_with("key1", "key2", "key3")
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_invalidate_prediction_cache_no_keys(self, mock_pool, mock_redis, mock_config):
        """Test prediction cache invalidation when no keys exist."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.keys.return_value = []
        
        cache_service = CacheService(mock_config)
        result = cache_service.invalidate_prediction_cache()
        
        assert result == 0
        mock_redis_instance.delete.assert_not_called()
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_invalidate_prediction_cache_with_pattern(self, mock_pool, mock_redis, mock_config):
        """Test prediction cache invalidation with custom pattern."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.keys.return_value = ["custom_key1", "custom_key2"]
        mock_redis_instance.delete.return_value = 2
        
        cache_service = CacheService(mock_config)
        result = cache_service.invalidate_prediction_cache("custom_pattern:*")
        
        assert result == 2
        mock_redis_instance.keys.assert_called_once_with("custom_pattern:*")
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_get_cache_stats_available(self, mock_pool, mock_redis, mock_config):
        """Test getting cache statistics when Redis is available."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.info.return_value = {
            "connected_clients": 5,
            "used_memory_human": "1.2M",
            "keyspace_hits": 100,
            "keyspace_misses": 20,
            "uptime_in_seconds": 3600
        }
        
        cache_service = CacheService(mock_config)
        stats = cache_service.get_cache_stats()
        
        assert stats["available"] is True
        assert stats["connected_clients"] == 5
        assert stats["used_memory"] == "1.2M"
        assert stats["keyspace_hits"] == 100
        assert stats["keyspace_misses"] == 20
        assert stats["uptime_seconds"] == 3600
        assert stats["hit_ratio"] == 100 / 120  # hits / (hits + misses)
        assert stats["redis_url"] == "redis://localhost:6379/0"
        assert stats["default_ttl"] == 300
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_get_cache_stats_unavailable(self, mock_pool, mock_redis, mock_config):
        """Test getting cache statistics when Redis is unavailable."""
        cache_service = CacheService(mock_config)
        cache_service._is_available = False
        cache_service._redis_client = None
        
        stats = cache_service.get_cache_stats()
        
        assert stats["available"] is False
        assert stats["redis_url"] == "redis://localhost:6379/0"
        assert stats["default_ttl"] == 300
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_get_cache_stats_info_error(self, mock_pool, mock_redis, mock_config):
        """Test getting cache statistics when Redis info() fails."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.info.side_effect = RedisError("Info failed")
        
        cache_service = CacheService(mock_config)
        stats = cache_service.get_cache_stats()
        
        assert stats["available"] is True
        assert "error" in stats
        assert stats["error"] == "Info failed"
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_close_cache_service(self, mock_pool, mock_redis, mock_config):
        """Test cache service cleanup."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        cache_service = CacheService(mock_config)
        cache_service.close()
        
        assert cache_service._redis_client is None
        assert cache_service._connection_pool is None
        assert cache_service._is_available is False
        mock_pool_instance.disconnect.assert_called_once()


class TestCacheServiceTTLBehavior:
    """Test TTL (Time To Live) behavior of cache service."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration for testing."""
        config = Mock(spec=AppConfig)
        config.redis_url = "redis://localhost:6379/0"
        config.cache_ttl = 300
        return config
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_ttl_behavior_with_custom_ttl(self, mock_pool, mock_redis, mock_config):
        """Test that custom TTL is used when provided."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.setex.return_value = True
        
        cache_service = CacheService(mock_config)
        cache_service.set("test_key", {"data": "test"}, ttl=600)
        
        args = mock_redis_instance.setex.call_args[0]
        assert args[1] == 600  # Custom TTL should be used
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_ttl_behavior_with_default_ttl(self, mock_pool, mock_redis, mock_config):
        """Test that default TTL is used when not provided."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.setex.return_value = True
        
        cache_service = CacheService(mock_config)
        cache_service.set("test_key", {"data": "test"})
        
        args = mock_redis_instance.setex.call_args[0]
        assert args[1] == 300  # Default TTL from config should be used


class TestCacheServiceFallbackMechanisms:
    """Test fallback mechanisms when Redis is unavailable."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration for testing."""
        config = Mock(spec=AppConfig)
        config.redis_url = "redis://localhost:6379/0"
        config.cache_ttl = 300
        return config
    
    def test_fallback_when_redis_unavailable_during_init(self, mock_config):
        """Test fallback behavior when Redis is unavailable during initialization."""
        with patch('services.cache_service.ConnectionPool.from_url') as mock_pool:
            mock_pool.side_effect = ConnectionError("Redis unavailable")
            
            cache_service = CacheService(mock_config)
            
            # Service should still be created but marked as unavailable
            assert cache_service._is_available is False
            assert cache_service._redis_client is None
            
            # All operations should return appropriate fallback values
            assert cache_service.get("test_key") is None
            assert cache_service.set("test_key", {"data": "test"}) is False
            assert cache_service.delete("test_key") is False
            assert cache_service.get_cached_prediction({"test": "input"}) is None
            assert cache_service.invalidate_prediction_cache() == 0
    
    @patch('services.cache_service.redis.Redis')
    @patch('services.cache_service.ConnectionPool.from_url')
    def test_fallback_when_redis_becomes_unavailable(self, mock_pool, mock_redis, mock_config):
        """Test fallback behavior when Redis becomes unavailable after initialization."""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        cache_service = CacheService(mock_config)
        
        # Initially available
        assert cache_service.is_available() is True
        
        # Redis becomes unavailable
        mock_redis_instance.ping.side_effect = ConnectionError("Connection lost")
        
        # Should detect unavailability and return fallback values
        assert cache_service.is_available() is False
        assert cache_service.get("test_key") is None
        assert cache_service.set("test_key", {"data": "test"}) is False


class TestCacheServiceGlobalInstance:
    """Test global cache service instance management."""
    
    def setup_method(self):
        """Reset global cache service before each test."""
        # Reset the global cache service instance
        import services.cache_service
        services.cache_service._cache_service = None
    
    def teardown_method(self):
        """Clean up global cache service after each test."""
        # Reset the global cache service instance
        import services.cache_service
        services.cache_service._cache_service = None
    
    def test_get_cache_service_singleton(self):
        """Test that get_cache_service returns singleton instance."""
        with patch('services.cache_service.CacheService') as mock_cache_class:
            mock_instance = Mock()
            mock_cache_class.return_value = mock_instance
            
            # First call should create instance
            service1 = get_cache_service()
            assert service1 == mock_instance
            mock_cache_class.assert_called_once()
            
            # Second call should return same instance
            service2 = get_cache_service()
            assert service2 == mock_instance
            assert service1 is service2
            # CacheService constructor should only be called once
            assert mock_cache_class.call_count == 1
    
    def test_close_cache_service_global(self):
        """Test closing global cache service instance."""
        with patch('services.cache_service.CacheService') as mock_cache_class:
            mock_instance = Mock()
            mock_cache_class.return_value = mock_instance
            
            # Get instance
            service = get_cache_service()
            assert service == mock_instance
            
            # Close service
            close_cache_service()
            mock_instance.close.assert_called_once()
            
            # Next call should create new instance
            service2 = get_cache_service()
            assert mock_cache_class.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__])