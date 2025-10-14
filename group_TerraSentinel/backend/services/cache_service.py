"""
Redis cache service for Terra Pulse-Dify integration.
Provides caching functionality with connection pooling, TTL management, and fallback mechanisms.
"""

import json
import hashlib
import logging
from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
import redis
from redis.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from backend.config.settings import get_config

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis-based cache service with connection pooling and error handling.
    
    Provides cache-aside pattern implementation with automatic fallback
    when Redis is unavailable.
    """
    
    def __init__(self, config=None):
        """
        Initialize cache service with Redis connection.
        
        Args:
            config: Optional configuration object. If None, uses global config.
        """
        self.config = config or get_config()
        self._redis_client = None
        self._connection_pool = None
        self._is_available = False
        
        # Cache key prefixes
        self.PREDICTION_PREFIX = "terra_pulse:prediction"
        self.DIFY_RESULT_PREFIX = "terra_pulse:dify_result"
        self.HEALTH_PREFIX = "terra_pulse:health"
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize Redis connection with connection pooling."""
        try:
            # Parse Redis URL for connection parameters
            redis_url = self.config.redis_url
            
            # Create connection pool
            self._connection_pool = ConnectionPool.from_url(
                redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30
            )
            
            # Create Redis client
            self._redis_client = redis.Redis(
                connection_pool=self._connection_pool,
                decode_responses=True
            )
            
            # Test connection
            self._redis_client.ping()
            self._is_available = True
            
            logger.info("Redis cache service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            self._is_available = False
            self._redis_client = None
    
    def _generate_cache_key(self, prefix: str, data: Dict[str, Any]) -> str:
        """
        Generate a consistent cache key from data.
        
        Args:
            prefix: Cache key prefix
            data: Data to generate key from
            
        Returns:
            str: Generated cache key
        """
        # Create a consistent string representation of the data
        data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        
        # Generate hash for the data
        data_hash = hashlib.md5(data_str.encode()).hexdigest()
        
        return f"{prefix}:{data_hash}"
    
    def _serialize_data(self, data: Any) -> str:
        """
        Serialize data for Redis storage.
        
        Args:
            data: Data to serialize
            
        Returns:
            str: Serialized data
        """
        return json.dumps(data, default=str, separators=(',', ':'))
    
    def _deserialize_data(self, data: str) -> Any:
        """
        Deserialize data from Redis.
        
        Args:
            data: Serialized data string
            
        Returns:
            Any: Deserialized data
        """
        return json.loads(data)
    
    def is_available(self) -> bool:
        """
        Check if Redis cache is available.
        
        Returns:
            bool: True if cache is available, False otherwise
        """
        if not self._is_available or not self._redis_client:
            return False
        
        try:
            self._redis_client.ping()
            return True
        except Exception:
            self._is_available = False
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Optional[Any]: Cached value or None if not found/error
        """
        if not self.is_available():
            logger.debug("Cache not available, returning None")
            return None
        
        try:
            cached_data = self._redis_client.get(key)
            if cached_data is None:
                logger.debug(f"Cache miss for key: {key}")
                return None
            
            logger.debug(f"Cache hit for key: {key}")
            return self._deserialize_data(cached_data)
            
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds. If None, uses config default.
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available():
            logger.debug("Cache not available, skipping set operation")
            return False
        
        try:
            ttl = ttl or self.config.cache_ttl
            serialized_value = self._serialize_data(value)
            
            result = self._redis_client.setex(key, ttl, serialized_value)
            
            if result:
                logger.debug(f"Cached value for key: {key} (TTL: {ttl}s)")
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            result = self._redis_client.delete(key)
            logger.debug(f"Deleted cache key: {key}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    def get_prediction_cache_key(self, prediction_input: Dict[str, Any]) -> str:
        """
        Generate cache key for Terra Pulse predictions.
        
        Args:
            prediction_input: Prediction input data
            
        Returns:
            str: Cache key for prediction
        """
        # Only use relevant fields for cache key generation
        cache_data = {
            "NDVI_mean_early": prediction_input.get("NDVI_mean_early"),
            "NDVI_median_early": prediction_input.get("NDVI_median_early"),
            "NDVI_std_early": prediction_input.get("NDVI_std_early"),
            "NDVI_mean_late": prediction_input.get("NDVI_mean_late"),
            "NDVI_median_late": prediction_input.get("NDVI_median_late"),
            "NDVI_std_late": prediction_input.get("NDVI_std_late"),
            "NDVI_delta_mean": prediction_input.get("NDVI_delta_mean"),
            "location": prediction_input.get("location"),
            "user_context": prediction_input.get("user_context")
        }
        
        return self._generate_cache_key(self.PREDICTION_PREFIX, cache_data)
    
    def get_dify_result_cache_key(self, dify_input: Dict[str, Any]) -> str:
        """
        Generate cache key for Dify workflow results.
        
        Args:
            dify_input: Dify workflow input data
            
        Returns:
            str: Cache key for Dify result
        """
        return self._generate_cache_key(self.DIFY_RESULT_PREFIX, dify_input)
    
    def cache_prediction(self, prediction_input: Dict[str, Any], 
                        prediction_result: Dict[str, Any], 
                        ttl: Optional[int] = None) -> bool:
        """
        Cache Terra Pulse prediction result.
        
        Args:
            prediction_input: Input data used for prediction
            prediction_result: Prediction result to cache
            ttl: Optional TTL override
            
        Returns:
            bool: True if cached successfully
        """
        cache_key = self.get_prediction_cache_key(prediction_input)
        
        # Add metadata to cached result
        cached_data = {
            "result": prediction_result,
            "cached_at": datetime.utcnow().isoformat(),
            "input_hash": hashlib.md5(
                json.dumps(prediction_input, sort_keys=True).encode()
            ).hexdigest()
        }
        
        return self.set(cache_key, cached_data, ttl)
    
    def get_cached_prediction(self, prediction_input: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached Terra Pulse prediction result.
        
        Args:
            prediction_input: Input data for prediction lookup
            
        Returns:
            Optional[Dict[str, Any]]: Cached prediction result or None
        """
        cache_key = self.get_prediction_cache_key(prediction_input)
        cached_data = self.get(cache_key)
        
        if cached_data and isinstance(cached_data, dict):
            return cached_data.get("result")
        
        return None
    
    def cache_dify_result(self, dify_input: Dict[str, Any], 
                         dify_result: Dict[str, Any], 
                         ttl: Optional[int] = None) -> bool:
        """
        Cache Dify workflow result.
        
        Args:
            dify_input: Input data sent to Dify
            dify_result: Dify workflow result to cache
            ttl: Optional TTL override
            
        Returns:
            bool: True if cached successfully
        """
        cache_key = self.get_dify_result_cache_key(dify_input)
        
        # Add metadata to cached result
        cached_data = {
            "result": dify_result,
            "cached_at": datetime.utcnow().isoformat(),
            "input_hash": hashlib.md5(
                json.dumps(dify_input, sort_keys=True).encode()
            ).hexdigest()
        }
        
        return self.set(cache_key, cached_data, ttl)
    
    def get_cached_dify_result(self, dify_input: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached Dify workflow result.
        
        Args:
            dify_input: Input data for Dify lookup
            
        Returns:
            Optional[Dict[str, Any]]: Cached Dify result or None
        """
        cache_key = self.get_dify_result_cache_key(dify_input)
        cached_data = self.get(cache_key)
        
        if cached_data and isinstance(cached_data, dict):
            return cached_data.get("result")
        
        return None
    
    def invalidate_prediction_cache(self, pattern: Optional[str] = None) -> int:
        """
        Invalidate prediction cache entries.
        
        Args:
            pattern: Optional pattern to match keys. If None, invalidates all predictions.
            
        Returns:
            int: Number of keys deleted
        """
        if not self.is_available():
            return 0
        
        try:
            search_pattern = pattern or f"{self.PREDICTION_PREFIX}:*"
            keys = self._redis_client.keys(search_pattern)
            
            if keys:
                deleted = self._redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} prediction cache entries")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Error invalidating prediction cache: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics and health information.
        
        Returns:
            Dict[str, Any]: Cache statistics
        """
        stats = {
            "available": self.is_available(),
            "redis_url": self.config.redis_url,
            "default_ttl": self.config.cache_ttl
        }
        
        if self.is_available():
            try:
                info = self._redis_client.info()
                stats.update({
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory_human", "unknown"),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                    "uptime_seconds": info.get("uptime_in_seconds", 0)
                })
                
                # Calculate hit ratio
                hits = stats["keyspace_hits"]
                misses = stats["keyspace_misses"]
                total = hits + misses
                stats["hit_ratio"] = (hits / total) if total > 0 else 0.0
                
            except Exception as e:
                logger.error(f"Error getting cache stats: {e}")
                stats["error"] = str(e)
        
        return stats
    
    def close(self):
        """Close Redis connection and cleanup resources."""
        if self._connection_pool:
            try:
                self._connection_pool.disconnect()
                logger.info("Redis connection pool closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection pool: {e}")
        
        self._redis_client = None
        self._connection_pool = None
        self._is_available = False


# Global cache service instance
_cache_service = None


def get_cache_service() -> CacheService:
    """
    Get global cache service instance.
    
    Returns:
        CacheService: Cache service singleton
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def close_cache_service():
    """Close global cache service instance."""
    global _cache_service
    if _cache_service:
        _cache_service.close()
        _cache_service = None