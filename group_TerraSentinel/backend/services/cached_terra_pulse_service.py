"""
Cached Terra Pulse service wrapper implementing cache-aside pattern.
Provides caching layer for Terra Pulse predictions with fallback mechanisms.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import asdict
from datetime import datetime, timedelta

from .terra_pulse_service import TerraPulseService, PredictionInput, PredictionOutput, TerraPulseModelError
from .cache_service import get_cache_service, CacheService
from backend.config.settings import AppConfig

logger = logging.getLogger(__name__)


class CachedTerraPulseService:
    """
    Cached wrapper for Terra Pulse service implementing cache-aside pattern.
    
    Provides automatic caching of predictions with configurable TTL and fallback
    mechanisms when cache is unavailable.
    """
    
    def __init__(self, config: AppConfig = None, cache_service: CacheService = None):
        """
        Initialize cached Terra Pulse service.
        
        Args:
            config: Optional configuration object
            cache_service: Optional cache service instance
        """
        self.config = config
        self.terra_pulse_service = TerraPulseService(config)
        self.cache_service = cache_service or get_cache_service()
        
        # Cache configuration
        self.prediction_cache_ttl = getattr(config, 'prediction_cache_ttl', 3600)  # 1 hour default
        self.enable_cache_warming = getattr(config, 'enable_cache_warming', False)
        
        logger.info("Cached Terra Pulse service initialized")
    
    def _convert_input_to_dict(self, input_data: PredictionInput) -> Dict[str, Any]:
        """
        Convert PredictionInput to dictionary for caching.
        
        Args:
            input_data: Prediction input data
            
        Returns:
            Dict[str, Any]: Input data as dictionary
        """
        return asdict(input_data)
    
    def _convert_output_to_dict(self, output_data: PredictionOutput) -> Dict[str, Any]:
        """
        Convert PredictionOutput to dictionary for caching.
        
        Args:
            output_data: Prediction output data
            
        Returns:
            Dict[str, Any]: Output data as dictionary
        """
        return asdict(output_data)
    
    def _convert_dict_to_output(self, output_dict: Dict[str, Any]) -> PredictionOutput:
        """
        Convert dictionary back to PredictionOutput.
        
        Args:
            output_dict: Output data as dictionary
            
        Returns:
            PredictionOutput: Prediction output object
        """
        return PredictionOutput(**output_dict)
    
    def predict(self, input_data: PredictionInput, use_cache: bool = True) -> PredictionOutput:
        """
        Perform cached prediction with cache-aside pattern and fallback mechanisms.
        
        Args:
            input_data: Prediction input data
            use_cache: Whether to use caching (default: True)
            
        Returns:
            PredictionOutput: Prediction result (cached or fresh)
            
        Raises:
            TerraPulseModelError: If prediction fails
        """
        start_time = time.time()
        cache_hit = False
        
        try:
            # Convert input to dictionary for cache key generation
            input_dict = self._convert_input_to_dict(input_data)
            
            # Try to get from cache first (cache-aside pattern)
            cached_result = None
            if use_cache and self.cache_service.is_available():
                cached_result = self.cache_service.get_cached_prediction(input_dict)
                
                if cached_result:
                    cache_hit = True
                    result = self._convert_dict_to_output(cached_result)
                    
                    # Update processing time to reflect cache retrieval
                    result.processing_time_ms = (time.time() - start_time) * 1000
                    
                    logger.debug(
                        f"Cache hit for prediction: location={input_data.location}, "
                        f"risk={result.degradation_risk}%"
                    )
                    
                    # Proactively warm cache if near expiration
                    if self.enable_cache_warming:
                        self.warm_cache_proactively(input_data)
                    
                    return result
            
            # Cache miss or cache disabled - try fresh prediction
            logger.debug(f"Cache miss for prediction: location={input_data.location}")
            
            try:
                result = self.terra_pulse_service.predict(input_data)
                
                # Cache the result if caching is enabled and available
                if use_cache and self.cache_service.is_available():
                    result_dict = self._convert_output_to_dict(result)
                    cache_success = self.cache_service.cache_prediction(
                        input_dict, 
                        result_dict, 
                        ttl=self.prediction_cache_ttl
                    )
                    
                    if cache_success:
                        logger.debug(f"Cached prediction result for location: {input_data.location}")
                    else:
                        logger.warning(f"Failed to cache prediction for location: {input_data.location}")
                
                return result
                
            except TerraPulseModelError as terra_error:
                # Terra Pulse service failed - try to return stale cache if available
                logger.warning(f"Terra Pulse service failed, attempting fallback to stale cache: {terra_error}")
                
                if use_cache and self.cache_service.is_available():
                    # Try to get any cached result, even if expired
                    stale_result = self._get_stale_cached_prediction(input_dict)
                    if stale_result:
                        logger.info(f"Returning stale cached result for location: {input_data.location}")
                        result = self._convert_dict_to_output(stale_result)
                        result.processing_time_ms = (time.time() - start_time) * 1000
                        return result
                
                # No fallback available, re-raise the original error
                raise terra_error
            
        except TerraPulseModelError:
            # Re-raise Terra Pulse specific errors
            raise
        except Exception as e:
            # Handle unexpected errors - try fallback to cache
            logger.error(f"Unexpected error in cached prediction: {str(e)}")
            
            if use_cache and self.cache_service.is_available():
                # Try to get any cached result as fallback
                stale_result = self._get_stale_cached_prediction(input_dict)
                if stale_result:
                    logger.info(f"Returning stale cached result due to error for location: {input_data.location}")
                    result = self._convert_dict_to_output(stale_result)
                    result.processing_time_ms = (time.time() - start_time) * 1000
                    return result
            
            # No fallback available
            processing_time = (time.time() - start_time) * 1000
            error_msg = f"Cached prediction failed: {str(e)}"
            logger.error(error_msg)
            raise TerraPulseModelError(error_msg, "cached_terra_pulse", e)
    
    def _get_stale_cached_prediction(self, input_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached prediction even if expired (for fallback scenarios).
        
        Args:
            input_dict: Input data dictionary for cache key generation
            
        Returns:
            Optional[Dict[str, Any]]: Stale cached result or None
        """
        try:
            cache_key = self.cache_service.get_prediction_cache_key(input_dict)
            
            # Try to get the value directly, bypassing TTL check
            if self.cache_service._redis_client:
                cached_data = self.cache_service._redis_client.get(cache_key)
                if cached_data:
                    deserialized_data = self.cache_service._deserialize_data(cached_data)
                    if isinstance(deserialized_data, dict):
                        return deserialized_data.get("result")
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving stale cache: {e}")
            return None
    
    def predict_with_cache_warming(self, input_data: PredictionInput) -> PredictionOutput:
        """
        Perform prediction with intelligent cache warming strategy.
        
        This method will refresh the cache proactively if the cached result
        is close to expiration and schedule background warming for related predictions.
        
        Args:
            input_data: Prediction input data
            
        Returns:
            PredictionOutput: Prediction result
        """
        # Get the prediction result
        result = self.predict(input_data, use_cache=True)
        
        # If cache warming is enabled, schedule related cache warming
        if self.enable_cache_warming and self.cache_service.is_available():
            try:
                # Generate related predictions for the same location with different NDVI scenarios
                self._schedule_related_cache_warming(input_data)
            except Exception as e:
                logger.warning(f"Failed to schedule related cache warming: {e}")
        
        return result
    
    def _schedule_related_cache_warming(self, base_input: PredictionInput) -> None:
        """
        Schedule cache warming for related predictions based on the current input.
        
        Args:
            base_input: Base input to generate related scenarios from
        """
        try:
            import threading
            
            def warm_related_predictions():
                """Background task to warm related predictions."""
                try:
                    # Generate variations of the input for different scenarios
                    variations = self._generate_input_variations(base_input)
                    
                    for variation in variations:
                        try:
                            # Check if already cached
                            input_dict = self._convert_input_to_dict(variation)
                            cached_result = self.cache_service.get_cached_prediction(input_dict)
                            
                            if not cached_result:
                                # Warm cache with this variation
                                self.predict(variation, use_cache=True)
                                logger.debug(f"Background warmed cache for {variation.location} variation")
                        
                        except Exception as e:
                            logger.warning(f"Failed to warm cache for variation: {e}")
                            continue
                
                except Exception as e:
                    logger.error(f"Error in background cache warming: {e}")
            
            # Start background warming thread
            warming_thread = threading.Thread(target=warm_related_predictions, daemon=True)
            warming_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to schedule background cache warming: {e}")
    
    def _generate_input_variations(self, base_input: PredictionInput) -> List[PredictionInput]:
        """
        Generate input variations for cache warming based on a base input.
        
        Args:
            base_input: Base input to generate variations from
            
        Returns:
            List[PredictionInput]: List of input variations
        """
        variations = []
        
        try:
            # Generate variations with different NDVI scenarios
            scenarios = [
                {"name": "slight_improvement", "delta": 0.05},
                {"name": "slight_degradation", "delta": -0.05},
                {"name": "seasonal_variation", "delta": 0.02},
                {"name": "drought_stress", "delta": -0.1}
            ]
            
            for scenario in scenarios:
                delta = scenario["delta"]
                
                # Create variation with NDVI adjustments
                variation = PredictionInput(
                    ndvi_mean_early=max(-1.0, min(1.0, base_input.ndvi_mean_early + delta)),
                    ndvi_median_early=max(-1.0, min(1.0, base_input.ndvi_median_early + delta)),
                    ndvi_std_early=base_input.ndvi_std_early,
                    ndvi_mean_late=max(-1.0, min(1.0, base_input.ndvi_mean_late + delta)),
                    ndvi_median_late=max(-1.0, min(1.0, base_input.ndvi_median_late + delta)),
                    ndvi_std_late=base_input.ndvi_std_late,
                    ndvi_delta_mean=base_input.ndvi_delta_mean + delta,
                    location=base_input.location,
                    user_context=f"{base_input.user_context}_{scenario['name']}"
                )
                
                variations.append(variation)
            
            return variations
            
        except Exception as e:
            logger.error(f"Error generating input variations: {e}")
            return []
    
    def invalidate_prediction_cache(self, location_pattern: Optional[str] = None) -> int:
        """
        Invalidate prediction cache entries.
        
        Args:
            location_pattern: Optional location pattern to match for selective invalidation
            
        Returns:
            int: Number of cache entries invalidated
        """
        if not self.cache_service.is_available():
            logger.warning("Cache service not available for invalidation")
            return 0
        
        try:
            if location_pattern:
                # For selective invalidation, we'd need to implement pattern matching
                # For now, just invalidate all predictions
                logger.info(f"Invalidating prediction cache (pattern: {location_pattern})")
            else:
                logger.info("Invalidating all prediction cache entries")
            
            return self.cache_service.invalidate_prediction_cache()
            
        except Exception as e:
            logger.error(f"Error invalidating prediction cache: {e}")
            return 0
    
    def invalidate_cache_by_age(self, max_age_hours: int = 24) -> int:
        """
        Invalidate cache entries older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours for cache entries
            
        Returns:
            int: Number of cache entries invalidated
        """
        if not self.cache_service.is_available():
            logger.warning("Cache service not available for age-based invalidation")
            return 0
        
        try:
            from datetime import datetime, timedelta
            
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            invalidated_count = 0
            
            # Get all prediction cache keys
            if self.cache_service._redis_client:
                pattern = f"{self.cache_service.PREDICTION_PREFIX}:*"
                keys = self.cache_service._redis_client.keys(pattern)
                
                for key in keys:
                    try:
                        # Get cached data to check timestamp
                        cached_data = self.cache_service.get(key)
                        if cached_data and isinstance(cached_data, dict):
                            cached_at_str = cached_data.get("cached_at")
                            if cached_at_str:
                                cached_at = datetime.fromisoformat(cached_at_str.replace('Z', '+00:00'))
                                if cached_at < cutoff_time:
                                    self.cache_service.delete(key)
                                    invalidated_count += 1
                    
                    except Exception as e:
                        logger.warning(f"Error checking cache entry age for key {key}: {e}")
                        continue
            
            logger.info(f"Invalidated {invalidated_count} cache entries older than {max_age_hours} hours")
            return invalidated_count
            
        except Exception as e:
            logger.error(f"Error in age-based cache invalidation: {e}")
            return 0
    
    def invalidate_cache_by_location(self, locations: List[str]) -> int:
        """
        Invalidate cache entries for specific locations.
        
        Args:
            locations: List of locations to invalidate cache for
            
        Returns:
            int: Number of cache entries invalidated
        """
        if not self.cache_service.is_available():
            logger.warning("Cache service not available for location-based invalidation")
            return 0
        
        try:
            invalidated_count = 0
            
            # Get all prediction cache keys
            if self.cache_service._redis_client:
                pattern = f"{self.cache_service.PREDICTION_PREFIX}:*"
                keys = self.cache_service._redis_client.keys(pattern)
                
                for key in keys:
                    try:
                        # Get cached data to check location
                        cached_data = self.cache_service.get(key)
                        if cached_data and isinstance(cached_data, dict):
                            result = cached_data.get("result", {})
                            cached_location = result.get("location", "")
                            
                            # Check if location matches any in the list
                            for location in locations:
                                if location.lower() in cached_location.lower():
                                    self.cache_service.delete(key)
                                    invalidated_count += 1
                                    logger.debug(f"Invalidated cache for location: {cached_location}")
                                    break
                    
                    except Exception as e:
                        logger.warning(f"Error checking cache entry location for key {key}: {e}")
                        continue
            
            logger.info(f"Invalidated {invalidated_count} cache entries for {len(locations)} locations")
            return invalidated_count
            
        except Exception as e:
            logger.error(f"Error in location-based cache invalidation: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for predictions.
        
        Returns:
            Dict[str, Any]: Cache statistics
        """
        base_stats = self.cache_service.get_cache_stats()
        
        # Add prediction-specific stats
        base_stats.update({
            "prediction_cache_ttl": self.prediction_cache_ttl,
            "cache_warming_enabled": self.enable_cache_warming,
            "service_type": "cached_terra_pulse"
        })
        
        return base_stats
    
    def warm_cache_for_common_locations(self, common_inputs: list[PredictionInput]) -> Dict[str, Any]:
        """
        Warm cache with predictions for common locations/scenarios.
        
        Args:
            common_inputs: List of common prediction inputs to pre-cache
            
        Returns:
            Dict[str, Any]: Cache warming results
        """
        if not self.enable_cache_warming:
            return {"status": "disabled", "warmed_count": 0}
        
        if not self.cache_service.is_available():
            return {"status": "cache_unavailable", "warmed_count": 0}
        
        warmed_count = 0
        errors = []
        
        logger.info(f"Starting cache warming for {len(common_inputs)} locations")
        
        for input_data in common_inputs:
            try:
                # Check if already cached
                input_dict = self._convert_input_to_dict(input_data)
                cached_result = self.cache_service.get_cached_prediction(input_dict)
                
                if not cached_result:
                    # Not cached, perform prediction to warm cache
                    result = self.predict(input_data, use_cache=True)
                    warmed_count += 1
                    logger.debug(f"Warmed cache for location: {input_data.location}")
                
            except Exception as e:
                error_msg = f"Failed to warm cache for {input_data.location}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        logger.info(f"Cache warming completed: {warmed_count} entries warmed, {len(errors)} errors")
        
        return {
            "status": "completed",
            "warmed_count": warmed_count,
            "total_requested": len(common_inputs),
            "errors": errors
        }
    
    def warm_cache_proactively(self, input_data: PredictionInput, refresh_threshold: float = 0.8) -> bool:
        """
        Proactively warm cache for a specific input if cache entry is near expiration.
        
        Args:
            input_data: Prediction input to check and potentially warm
            refresh_threshold: Refresh cache when TTL is below this fraction (0.0-1.0)
            
        Returns:
            bool: True if cache was warmed, False otherwise
        """
        if not self.cache_service.is_available():
            return False
        
        try:
            input_dict = self._convert_input_to_dict(input_data)
            cache_key = self.cache_service.get_prediction_cache_key(input_dict)
            
            # Check if key exists and get TTL
            if self.cache_service._redis_client:
                ttl = self.cache_service._redis_client.ttl(cache_key)
                
                # If key exists and TTL is below threshold, refresh it
                if ttl > 0 and ttl < (self.prediction_cache_ttl * refresh_threshold):
                    logger.debug(f"Proactively refreshing cache for {input_data.location} (TTL: {ttl}s)")
                    
                    # Perform fresh prediction to update cache
                    self.predict(input_data, use_cache=False)  # Force fresh prediction
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in proactive cache warming: {e}")
            return False
    
    def warm_cache_by_pattern(self, location_patterns: List[str], 
                             ndvi_ranges: Dict[str, tuple] = None) -> Dict[str, Any]:
        """
        Warm cache for predictions matching location patterns and NDVI ranges.
        
        Args:
            location_patterns: List of location patterns to generate predictions for
            ndvi_ranges: Optional NDVI value ranges for synthetic data generation
            
        Returns:
            Dict[str, Any]: Cache warming results
        """
        if not self.enable_cache_warming:
            return {"status": "disabled", "warmed_count": 0}
        
        if not ndvi_ranges:
            # Default NDVI ranges for different scenarios
            ndvi_ranges = {
                "healthy": (0.4, 0.8),
                "moderate_stress": (0.2, 0.4),
                "high_stress": (0.0, 0.2)
            }
        
        warmed_count = 0
        errors = []
        
        logger.info(f"Starting pattern-based cache warming for {len(location_patterns)} locations")
        
        for location in location_patterns:
            for scenario, (min_ndvi, max_ndvi) in ndvi_ranges.items():
                try:
                    # Generate synthetic but realistic NDVI data
                    import random
                    
                    base_ndvi_early = random.uniform(min_ndvi, max_ndvi)
                    base_ndvi_late = base_ndvi_early + random.uniform(-0.1, 0.05)  # Slight seasonal change
                    
                    synthetic_input = PredictionInput(
                        ndvi_mean_early=base_ndvi_early,
                        ndvi_median_early=base_ndvi_early * 0.95,
                        ndvi_std_early=random.uniform(0.05, 0.15),
                        ndvi_mean_late=base_ndvi_late,
                        ndvi_median_late=base_ndvi_late * 0.95,
                        ndvi_std_late=random.uniform(0.05, 0.15),
                        ndvi_delta_mean=base_ndvi_late - base_ndvi_early,
                        location=location,
                        user_context=f"synthetic_{scenario}"
                    )
                    
                    # Check if already cached
                    input_dict = self._convert_input_to_dict(synthetic_input)
                    cached_result = self.cache_service.get_cached_prediction(input_dict)
                    
                    if not cached_result:
                        # Warm cache with synthetic prediction
                        result = self.predict(synthetic_input, use_cache=True)
                        warmed_count += 1
                        logger.debug(f"Warmed cache for {location} ({scenario} scenario)")
                
                except Exception as e:
                    error_msg = f"Failed to warm cache for {location} ({scenario}): {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
        
        logger.info(f"Pattern-based cache warming completed: {warmed_count} entries warmed")
        
        return {
            "status": "completed",
            "warmed_count": warmed_count,
            "total_patterns": len(location_patterns) * len(ndvi_ranges),
            "errors": errors
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check for cached Terra Pulse service.
        
        Returns:
            Dict[str, Any]: Health check results
        """
        # Check underlying Terra Pulse service
        terra_pulse_health = await self.terra_pulse_service._perform_health_check()
        
        # Check cache service
        cache_stats = self.cache_service.get_cache_stats()
        
        return {
            "service": "cached_terra_pulse",
            "terra_pulse_status": terra_pulse_health.status.value,
            "terra_pulse_message": terra_pulse_health.message,
            "cache_available": cache_stats["available"],
            "cache_hit_ratio": cache_stats.get("hit_ratio", 0.0),
            "overall_status": "healthy" if (
                terra_pulse_health.status.value == "healthy" and 
                (cache_stats["available"] or True)  # Cache is optional
            ) else "degraded"
        }
    
    def manage_cache_lifecycle(self) -> Dict[str, Any]:
        """
        Perform automatic cache lifecycle management.
        
        This includes:
        - Cleaning up expired entries
        - Managing cache size
        - Optimizing cache performance
        
        Returns:
            Dict[str, Any]: Cache management results
        """
        if not self.cache_service.is_available():
            return {"status": "cache_unavailable", "actions_taken": []}
        
        actions_taken = []
        
        try:
            # 1. Clean up old entries (older than 7 days)
            old_entries_cleaned = self.invalidate_cache_by_age(max_age_hours=168)  # 7 days
            if old_entries_cleaned > 0:
                actions_taken.append(f"Cleaned {old_entries_cleaned} old cache entries")
            
            # 2. Check cache memory usage and clean if needed
            cache_stats = self.cache_service.get_cache_stats()
            if cache_stats.get("available"):
                try:
                    # Get memory info from Redis
                    if self.cache_service._redis_client:
                        info = self.cache_service._redis_client.info("memory")
                        used_memory = info.get("used_memory", 0)
                        max_memory = info.get("maxmemory", 0)
                        
                        # If using more than 80% of max memory, clean up more aggressively
                        if max_memory > 0 and used_memory > (max_memory * 0.8):
                            aggressive_cleanup = self.invalidate_cache_by_age(max_age_hours=24)  # 1 day
                            actions_taken.append(f"Aggressive cleanup: removed {aggressive_cleanup} entries")
                
                except Exception as e:
                    logger.warning(f"Could not check memory usage: {e}")
            
            # 3. Warm cache for common scenarios if enabled
            if self.enable_cache_warming:
                # Define common locations for cache warming
                common_locations = [
                    "Baringo County, Kenya",
                    "Turkana County, Kenya", 
                    "Marsabit County, Kenya",
                    "Samburu County, Kenya"
                ]
                
                warming_result = self.warm_cache_by_pattern(common_locations)
                if warming_result.get("warmed_count", 0) > 0:
                    actions_taken.append(f"Warmed cache for {warming_result['warmed_count']} common scenarios")
            
            logger.info(f"Cache lifecycle management completed: {len(actions_taken)} actions taken")
            
            return {
                "status": "completed",
                "actions_taken": actions_taken,
                "cache_stats": cache_stats
            }
            
        except Exception as e:
            logger.error(f"Error in cache lifecycle management: {e}")
            return {
                "status": "error",
                "error": str(e),
                "actions_taken": actions_taken
            }
    
    def get_cache_performance_metrics(self) -> Dict[str, Any]:
        """
        Get detailed cache performance metrics.
        
        Returns:
            Dict[str, Any]: Cache performance metrics
        """
        if not self.cache_service.is_available():
            return {"status": "cache_unavailable"}
        
        try:
            base_stats = self.cache_service.get_cache_stats()
            
            # Add prediction-specific metrics
            prediction_metrics = {
                "prediction_cache_ttl": self.prediction_cache_ttl,
                "cache_warming_enabled": self.enable_cache_warming,
                "service_type": "cached_terra_pulse"
            }
            
            # Get cache key count for predictions
            if self.cache_service._redis_client:
                pattern = f"{self.cache_service.PREDICTION_PREFIX}:*"
                prediction_keys = self.cache_service._redis_client.keys(pattern)
                prediction_metrics["prediction_cache_entries"] = len(prediction_keys)
                
                # Calculate average TTL for prediction entries
                ttls = []
                for key in prediction_keys[:100]:  # Sample first 100 keys
                    try:
                        ttl = self.cache_service._redis_client.ttl(key)
                        if ttl > 0:
                            ttls.append(ttl)
                    except Exception:
                        continue
                
                if ttls:
                    prediction_metrics["average_ttl_seconds"] = sum(ttls) / len(ttls)
                    prediction_metrics["min_ttl_seconds"] = min(ttls)
                    prediction_metrics["max_ttl_seconds"] = max(ttls)
            
            base_stats.update(prediction_metrics)
            return base_stats
            
        except Exception as e:
            logger.error(f"Error getting cache performance metrics: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the Terra Pulse model and caching.
        
        Returns:
            Dict[str, Any]: Model and cache information
        """
        model_info = self.terra_pulse_service.get_model_info()
        cache_stats = self.get_cache_stats()
        
        return {
            "model": model_info,
            "cache": cache_stats
        }
    
    def shutdown(self) -> None:
        """
        Shutdown the cached Terra Pulse service.
        """
        logger.info("Shutting down cached Terra Pulse service...")
        
        if self.terra_pulse_service:
            self.terra_pulse_service.shutdown()
        
        # Note: We don't close the cache service here as it might be shared
        # The cache service should be closed at the application level