"""
Tests for cached Terra Pulse service caching strategies.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from backend.services.cached_terra_pulse_service import CachedTerraPulseService
from backend.services.terra_pulse_service import PredictionInput, PredictionOutput, TerraPulseModelError
from backend.services.cache_service import CacheService
from backend.config.settings import AppConfig


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = Mock(spec=AppConfig)
    config.terra_pulse_model_path = "test_model.onnx"
    config.prediction_cache_ttl = 3600
    config.enable_cache_warming = True
    config.cache_ttl = 3600
    config.redis_url = "redis://localhost:6379/0"
    return config


@pytest.fixture
def mock_cache_service():
    """Create mock cache service."""
    cache_service = Mock(spec=CacheService)
    cache_service.is_available.return_value = True
    cache_service.get_cached_prediction.return_value = None
    cache_service.cache_prediction.return_value = True
    cache_service.get_cache_stats.return_value = {
        "available": True,
        "hit_ratio": 0.75,
        "keyspace_hits": 100,
        "keyspace_misses": 25
    }
    # Add cache prefixes
    cache_service.PREDICTION_PREFIX = "terra_pulse:prediction"
    cache_service.DIFY_RESULT_PREFIX = "terra_pulse:dify_result"
    cache_service.HEALTH_PREFIX = "terra_pulse:health"
    return cache_service


@pytest.fixture
def mock_terra_pulse_service():
    """Create mock Terra Pulse service."""
    service = Mock()
    
    # Mock prediction result
    mock_result = PredictionOutput(
        location="Test Location",
        degradation_risk=65,
        risk_factors=["moderate_ndvi_drop"],
        recommended_action_key="increase_soil_cover",
        confidence=0.78,
        user_context="test_user",
        raw_prediction=0.65,
        processing_time_ms=150.0
    )
    
    service.predict.return_value = mock_result
    return service


@pytest.fixture
def sample_input():
    """Create sample prediction input."""
    return PredictionInput(
        ndvi_mean_early=0.45,
        ndvi_median_early=0.43,
        ndvi_std_early=0.12,
        ndvi_mean_late=0.38,
        ndvi_median_late=0.36,
        ndvi_std_late=0.15,
        ndvi_delta_mean=-0.07,
        location="Test Location",
        user_context="test_user"
    )


class TestCachedTerraPulseService:
    """Test cached Terra Pulse service caching strategies."""
    
    def test_cache_aside_pattern_cache_hit(self, mock_config, mock_cache_service, mock_terra_pulse_service, sample_input):
        """Test cache-aside pattern with cache hit."""
        # Setup cached result
        cached_result = {
            "location": "Test Location",
            "degradation_risk": 65,
            "risk_factors": ["moderate_ndvi_drop"],
            "recommended_action_key": "increase_soil_cover",
            "confidence": 0.78,
            "user_context": "test_user",
            "raw_prediction": 0.65,
            "processing_time_ms": 150.0
        }
        mock_cache_service.get_cached_prediction.return_value = cached_result
        
        # Create service with mocks
        with patch('services.cached_terra_pulse_service.TerraPulseService', return_value=mock_terra_pulse_service):
            service = CachedTerraPulseService(mock_config, mock_cache_service)
            
            # Perform prediction
            result = service.predict(sample_input)
            
            # Verify cache was checked
            mock_cache_service.get_cached_prediction.assert_called_once()
            
            # Verify Terra Pulse service was not called (cache hit)
            mock_terra_pulse_service.predict.assert_not_called()
            
            # Verify result
            assert result.location == "Test Location"
            assert result.degradation_risk == 65
    
    def test_cache_aside_pattern_cache_miss(self, mock_config, mock_cache_service, mock_terra_pulse_service, sample_input):
        """Test cache-aside pattern with cache miss."""
        # Setup cache miss
        mock_cache_service.get_cached_prediction.return_value = None
        
        # Create service with mocks
        with patch('services.cached_terra_pulse_service.TerraPulseService', return_value=mock_terra_pulse_service):
            service = CachedTerraPulseService(mock_config, mock_cache_service)
            
            # Perform prediction
            result = service.predict(sample_input)
            
            # Verify cache was checked
            mock_cache_service.get_cached_prediction.assert_called_once()
            
            # Verify Terra Pulse service was called (cache miss)
            mock_terra_pulse_service.predict.assert_called_once_with(sample_input)
            
            # Verify result was cached
            mock_cache_service.cache_prediction.assert_called_once()
            
            # Verify result
            assert result.location == "Test Location"
            assert result.degradation_risk == 65
    
    def test_fallback_to_stale_cache_on_service_failure(self, mock_config, mock_cache_service, mock_terra_pulse_service, sample_input):
        """Test fallback to stale cache when Terra Pulse service fails."""
        # Setup cache miss for fresh cache
        mock_cache_service.get_cached_prediction.return_value = None
        
        # Setup Terra Pulse service failure
        mock_terra_pulse_service.predict.side_effect = TerraPulseModelError("Service unavailable", "terra_pulse")
        
        # Setup stale cache retrieval
        stale_result = {
            "location": "Test Location",
            "degradation_risk": 60,
            "risk_factors": ["moderate_ndvi_drop"],
            "recommended_action_key": "increase_soil_cover",
            "confidence": 0.75,
            "user_context": "test_user",
            "raw_prediction": 0.60,
            "processing_time_ms": 120.0
        }
        
        # Mock Redis client for stale cache retrieval
        mock_redis_client = Mock()
        mock_redis_client.get.return_value = '{"result": ' + str(stale_result).replace("'", '"') + '}'
        mock_cache_service._redis_client = mock_redis_client
        mock_cache_service._deserialize_data.return_value = {"result": stale_result}
        
        # Create service with mocks
        with patch('services.cached_terra_pulse_service.TerraPulseService', return_value=mock_terra_pulse_service):
            service = CachedTerraPulseService(mock_config, mock_cache_service)
            
            # Perform prediction - should not raise exception due to fallback
            result = service.predict(sample_input)
            
            # Verify Terra Pulse service was called and failed
            mock_terra_pulse_service.predict.assert_called_once()
            
            # Verify stale cache was retrieved
            mock_redis_client.get.assert_called_once()
            
            # Verify result from stale cache
            assert result.location == "Test Location"
            assert result.degradation_risk == 60
    
    def test_cache_warming_for_common_locations(self, mock_config, mock_cache_service, mock_terra_pulse_service):
        """Test cache warming for common locations."""
        # Setup cache service
        mock_cache_service.get_cached_prediction.return_value = None  # No cached results
        
        # Create service with mocks
        with patch('services.cached_terra_pulse_service.TerraPulseService', return_value=mock_terra_pulse_service):
            service = CachedTerraPulseService(mock_config, mock_cache_service)
            
            # Create common inputs for warming
            common_inputs = [
                PredictionInput(
                    ndvi_mean_early=0.5, ndvi_median_early=0.48, ndvi_std_early=0.1,
                    ndvi_mean_late=0.45, ndvi_median_late=0.43, ndvi_std_late=0.12,
                    ndvi_delta_mean=-0.05, location="Location 1", user_context="farmer"
                ),
                PredictionInput(
                    ndvi_mean_early=0.4, ndvi_median_early=0.38, ndvi_std_early=0.15,
                    ndvi_mean_late=0.35, ndvi_median_late=0.33, ndvi_std_late=0.18,
                    ndvi_delta_mean=-0.05, location="Location 2", user_context="official"
                )
            ]
            
            # Perform cache warming
            result = service.warm_cache_for_common_locations(common_inputs)
            
            # Verify predictions were made for warming
            assert mock_terra_pulse_service.predict.call_count == 2
            
            # Verify cache was populated
            assert mock_cache_service.cache_prediction.call_count == 2
            
            # Verify result
            assert result["status"] == "completed"
            assert result["warmed_count"] == 2
            assert result["total_requested"] == 2
    
    def test_proactive_cache_warming(self, mock_config, mock_cache_service, mock_terra_pulse_service, sample_input):
        """Test proactive cache warming when TTL is low."""
        # Setup cache service with TTL checking
        mock_redis_client = Mock()
        mock_redis_client.ttl.return_value = 300  # 5 minutes remaining (below threshold)
        mock_cache_service._redis_client = mock_redis_client
        
        # Create service with mocks
        with patch('services.cached_terra_pulse_service.TerraPulseService', return_value=mock_terra_pulse_service):
            service = CachedTerraPulseService(mock_config, mock_cache_service)
            service.prediction_cache_ttl = 3600  # 1 hour
            
            # Test proactive warming
            result = service.warm_cache_proactively(sample_input, refresh_threshold=0.8)
            
            # Verify TTL was checked
            mock_redis_client.ttl.assert_called_once()
            
            # Verify fresh prediction was made (cache refresh)
            mock_terra_pulse_service.predict.assert_called_once()
            
            # Verify warming occurred
            assert result is True
    
    def test_cache_invalidation_by_age(self, mock_config, mock_cache_service, mock_terra_pulse_service):
        """Test cache invalidation by age."""
        # Setup Redis client mock
        mock_redis_client = Mock()
        
        # Mock cache keys
        cache_keys = ["terra_pulse:prediction:key1", "terra_pulse:prediction:key2", "terra_pulse:prediction:key3"]
        mock_redis_client.keys.return_value = cache_keys
        
        # Mock cached data with different ages
        old_time = (datetime.utcnow() - timedelta(hours=25)).isoformat()  # 25 hours old
        recent_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()  # 1 hour old
        
        cached_data = [
            {"result": {}, "cached_at": old_time},      # Should be invalidated
            {"result": {}, "cached_at": recent_time},   # Should be kept
            {"result": {}, "cached_at": old_time}       # Should be invalidated
        ]
        
        mock_cache_service.get.side_effect = cached_data
        mock_cache_service._redis_client = mock_redis_client
        
        # Create service with mocks
        with patch('services.cached_terra_pulse_service.TerraPulseService', return_value=mock_terra_pulse_service):
            service = CachedTerraPulseService(mock_config, mock_cache_service)
            
            # Perform age-based invalidation (24 hours)
            invalidated_count = service.invalidate_cache_by_age(max_age_hours=24)
            
            # Verify keys were retrieved
            mock_redis_client.keys.assert_called_once()
            
            # Verify cache entries were checked
            assert mock_cache_service.get.call_count == 3
            
            # Verify old entries were deleted (2 out of 3)
            assert mock_cache_service.delete.call_count == 2
            assert invalidated_count == 2
    
    def test_cache_invalidation_by_location(self, mock_config, mock_cache_service, mock_terra_pulse_service):
        """Test cache invalidation by location."""
        # Setup Redis client mock
        mock_redis_client = Mock()
        
        # Mock cache keys
        cache_keys = ["terra_pulse:prediction:key1", "terra_pulse:prediction:key2", "terra_pulse:prediction:key3"]
        mock_redis_client.keys.return_value = cache_keys
        
        # Mock cached data with different locations
        cached_data = [
            {"result": {"location": "Baringo County, Kenya"}},
            {"result": {"location": "Nairobi County, Kenya"}},
            {"result": {"location": "Turkana County, Kenya"}}
        ]
        
        mock_cache_service.get.side_effect = cached_data
        mock_cache_service._redis_client = mock_redis_client
        
        # Create service with mocks
        with patch('services.cached_terra_pulse_service.TerraPulseService', return_value=mock_terra_pulse_service):
            service = CachedTerraPulseService(mock_config, mock_cache_service)
            
            # Perform location-based invalidation
            locations_to_invalidate = ["Baringo", "Turkana"]
            invalidated_count = service.invalidate_cache_by_location(locations_to_invalidate)
            
            # Verify keys were retrieved
            mock_redis_client.keys.assert_called_once()
            
            # Verify cache entries were checked
            assert mock_cache_service.get.call_count == 3
            
            # Verify matching entries were deleted (2 out of 3)
            assert mock_cache_service.delete.call_count == 2
            assert invalidated_count == 2
    
    def test_cache_lifecycle_management(self, mock_config, mock_cache_service, mock_terra_pulse_service):
        """Test automatic cache lifecycle management."""
        # Setup cache service
        mock_cache_service.get_cache_stats.return_value = {
            "available": True,
            "used_memory": 1000000,
            "maxmemory": 2000000
        }
        
        # Setup Redis client mock
        mock_redis_client = Mock()
        mock_redis_client.info.return_value = {
            "used_memory": 1000000,
            "maxmemory": 2000000
        }
        mock_cache_service._redis_client = mock_redis_client
        
        # Create service with mocks
        with patch('services.cached_terra_pulse_service.TerraPulseService', return_value=mock_terra_pulse_service):
            service = CachedTerraPulseService(mock_config, mock_cache_service)
            
            # Mock invalidation methods
            service.invalidate_cache_by_age = Mock(return_value=5)
            service.warm_cache_by_pattern = Mock(return_value={"warmed_count": 3})
            
            # Perform lifecycle management
            result = service.manage_cache_lifecycle()
            
            # Verify management actions were taken
            assert result["status"] == "completed"
            assert len(result["actions_taken"]) > 0
            
            # Verify old entries were cleaned
            service.invalidate_cache_by_age.assert_called()
            
            # Verify cache warming was performed
            service.warm_cache_by_pattern.assert_called()
    
    def test_cache_performance_metrics(self, mock_config, mock_cache_service, mock_terra_pulse_service):
        """Test cache performance metrics collection."""
        # Setup cache service
        mock_cache_service.get_cache_stats.return_value = {
            "available": True,
            "hit_ratio": 0.85,
            "keyspace_hits": 170,
            "keyspace_misses": 30
        }
        
        # Setup Redis client mock
        mock_redis_client = Mock()
        prediction_keys = ["terra_pulse:prediction:key1", "terra_pulse:prediction:key2"]
        mock_redis_client.keys.return_value = prediction_keys
        mock_redis_client.ttl.side_effect = [1800, 2400]  # Different TTLs
        mock_cache_service._redis_client = mock_redis_client
        
        # Create service with mocks
        with patch('services.cached_terra_pulse_service.TerraPulseService', return_value=mock_terra_pulse_service):
            service = CachedTerraPulseService(mock_config, mock_cache_service)
            
            # Get performance metrics
            metrics = service.get_cache_performance_metrics()
            
            # Verify metrics structure
            assert metrics["prediction_cache_ttl"] == 3600
            assert metrics["cache_warming_enabled"] is True
            assert metrics["service_type"] == "cached_terra_pulse"
            assert metrics["prediction_cache_entries"] == 2
            assert "average_ttl_seconds" in metrics
            assert metrics["hit_ratio"] == 0.85
    
    def test_cache_unavailable_fallback(self, mock_config, mock_cache_service, mock_terra_pulse_service, sample_input):
        """Test behavior when cache is unavailable."""
        # Setup cache as unavailable
        mock_cache_service.is_available.return_value = False
        
        # Create service with mocks
        with patch('services.cached_terra_pulse_service.TerraPulseService', return_value=mock_terra_pulse_service):
            service = CachedTerraPulseService(mock_config, mock_cache_service)
            
            # Perform prediction
            result = service.predict(sample_input)
            
            # Verify cache was not used
            mock_cache_service.get_cached_prediction.assert_not_called()
            mock_cache_service.cache_prediction.assert_not_called()
            
            # Verify Terra Pulse service was called directly
            mock_terra_pulse_service.predict.assert_called_once_with(sample_input)
            
            # Verify result
            assert result.location == "Test Location"
            assert result.degradation_risk == 65


if __name__ == "__main__":
    pytest.main([__file__])