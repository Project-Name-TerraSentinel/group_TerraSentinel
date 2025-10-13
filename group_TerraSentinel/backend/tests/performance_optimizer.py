"""
Performance optimization utilities for Terra Pulse-Dify integration.
Analyzes performance metrics and suggests optimizations.
"""

import json
import time
import statistics
import redis
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

# Import services for analysis
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.cache_service import CacheService
from backend.config.settings import get_config


@dataclass
class PerformanceProfile:
    """Performance profile for a specific operation."""
    operation_name: str
    sample_count: int
    mean_time_ms: float
    median_time_ms: float
    p95_time_ms: float
    p99_time_ms: float
    min_time_ms: float
    max_time_ms: float
    success_rate: float
    cache_hit_rate: Optional[float] = None
    memory_usage_mb: Optional[float] = None


@dataclass
class OptimizationRecommendation:
    """Optimization recommendation."""
    category: str
    priority: str  # "high", "medium", "low"
    description: str
    expected_improvement: str
    implementation_effort: str  # "low", "medium", "high"
    code_changes: List[str]


class PerformanceAnalyzer:
    """Analyzes performance metrics and suggests optimizations."""
    
    def __init__(self):
        self.config = get_config()
        self.cache_service = CacheService(self.config)
        self.performance_data = {}
    
    def collect_performance_metrics(self, operation_name: str, 
                                  response_times: List[float],
                                  success_count: int,
                                  total_count: int,
                                  cache_hits: Optional[int] = None,
                                  cache_total: Optional[int] = None,
                                  memory_usage: Optional[float] = None) -> PerformanceProfile:
        """Collect and analyze performance metrics for an operation."""
        
        if not response_times:
            raise ValueError("No response times provided")
        
        # Calculate statistics
        sorted_times = sorted(response_times)
        sample_count = len(response_times)
        
        profile = PerformanceProfile(
            operation_name=operation_name,
            sample_count=sample_count,
            mean_time_ms=statistics.mean(response_times),
            median_time_ms=statistics.median(response_times),
            p95_time_ms=self._percentile(sorted_times, 95),
            p99_time_ms=self._percentile(sorted_times, 99),
            min_time_ms=min(response_times),
            max_time_ms=max(response_times),
            success_rate=success_count / total_count if total_count > 0 else 0,
            cache_hit_rate=cache_hits / cache_total if cache_total and cache_total > 0 else None,
            memory_usage_mb=memory_usage
        )
        
        self.performance_data[operation_name] = profile
        return profile
    
    def _percentile(self, sorted_data: List[float], percentile: int) -> float:
        """Calculate percentile of sorted data."""
        if not sorted_data:
            return 0.0
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def analyze_cache_performance(self) -> Dict[str, Any]:
        """Analyze cache performance and effectiveness."""
        try:
            cache_stats = self.cache_service.get_cache_stats()
            
            analysis = {
                "cache_available": cache_stats.get("available", False),
                "total_keys": cache_stats.get("total_keys", 0),
                "hit_ratio": cache_stats.get("hit_ratio", 0.0),
                "memory_usage": cache_stats.get("memory_usage", 0),
                "recommendations": []
            }
            
            # Analyze hit ratio
            hit_ratio = analysis["hit_ratio"]
            if hit_ratio < 0.3:
                analysis["recommendations"].append({
                    "type": "cache_hit_ratio",
                    "severity": "high",
                    "message": f"Low cache hit ratio ({hit_ratio:.1%}). Consider adjusting cache keys or TTL.",
                    "suggestions": [
                        "Review cache key generation strategy",
                        "Increase cache TTL for stable predictions",
                        "Implement cache warming for common requests"
                    ]
                })
            elif hit_ratio < 0.6:
                analysis["recommendations"].append({
                    "type": "cache_hit_ratio",
                    "severity": "medium",
                    "message": f"Moderate cache hit ratio ({hit_ratio:.1%}). Room for improvement.",
                    "suggestions": [
                        "Analyze request patterns for better caching",
                        "Consider predictive cache warming"
                    ]
                })
            
            # Analyze memory usage
            memory_usage = analysis["memory_usage"]
            if memory_usage > 100 * 1024 * 1024:  # 100MB
                analysis["recommendations"].append({
                    "type": "cache_memory",
                    "severity": "medium",
                    "message": f"High cache memory usage ({memory_usage / 1024 / 1024:.1f}MB).",
                    "suggestions": [
                        "Implement cache size limits",
                        "Use more aggressive TTL for large objects",
                        "Consider cache compression"
                    ]
                })
            
            return analysis
            
        except Exception as e:
            return {
                "cache_available": False,
                "error": str(e),
                "recommendations": [{
                    "type": "cache_error",
                    "severity": "high",
                    "message": "Cache analysis failed. Check Redis connectivity.",
                    "suggestions": ["Verify Redis configuration and connectivity"]
                }]
            }
    
    def generate_optimization_recommendations(self) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on performance analysis."""
        recommendations = []
        
        # Analyze each operation
        for operation_name, profile in self.performance_data.items():
            recommendations.extend(self._analyze_operation_performance(profile))
        
        # Add cache-specific recommendations
        cache_analysis = self.analyze_cache_performance()
        for cache_rec in cache_analysis.get("recommendations", []):
            recommendations.append(self._convert_cache_recommendation(cache_rec))
        
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.priority, 3))
        
        return recommendations
    
    def _analyze_operation_performance(self, profile: PerformanceProfile) -> List[OptimizationRecommendation]:
        """Analyze performance profile and generate recommendations."""
        recommendations = []
        
        # Response time analysis
        if profile.p95_time_ms > 2000:  # 2 seconds
            recommendations.append(OptimizationRecommendation(
                category="response_time",
                priority="high",
                description=f"{profile.operation_name} P95 response time is {profile.p95_time_ms:.0f}ms",
                expected_improvement="30-50% response time reduction",
                implementation_effort="medium",
                code_changes=[
                    "Implement async processing for Dify workflows",
                    "Add connection pooling for external APIs",
                    "Optimize data transformation pipelines"
                ]
            ))
        elif profile.p95_time_ms > 1000:  # 1 second
            recommendations.append(OptimizationRecommendation(
                category="response_time",
                priority="medium",
                description=f"{profile.operation_name} P95 response time is {profile.p95_time_ms:.0f}ms",
                expected_improvement="15-30% response time reduction",
                implementation_effort="low",
                code_changes=[
                    "Optimize JSON serialization/deserialization",
                    "Reduce unnecessary data copying",
                    "Implement request batching where possible"
                ]
            ))
        
        # Success rate analysis
        if profile.success_rate < 0.95:
            recommendations.append(OptimizationRecommendation(
                category="reliability",
                priority="high",
                description=f"{profile.operation_name} success rate is {profile.success_rate:.1%}",
                expected_improvement="Improve reliability to >99%",
                implementation_effort="medium",
                code_changes=[
                    "Implement circuit breaker pattern",
                    "Add comprehensive retry logic",
                    "Improve error handling and fallbacks"
                ]
            ))
        
        # Cache hit rate analysis
        if profile.cache_hit_rate is not None and profile.cache_hit_rate < 0.5:
            recommendations.append(OptimizationRecommendation(
                category="caching",
                priority="medium",
                description=f"{profile.operation_name} cache hit rate is {profile.cache_hit_rate:.1%}",
                expected_improvement="20-40% response time improvement",
                implementation_effort="low",
                code_changes=[
                    "Optimize cache key generation",
                    "Implement cache warming strategies",
                    "Adjust cache TTL based on data patterns"
                ]
            ))
        
        # Memory usage analysis
        if profile.memory_usage_mb and profile.memory_usage_mb > 500:  # 500MB
            recommendations.append(OptimizationRecommendation(
                category="memory",
                priority="medium",
                description=f"{profile.operation_name} uses {profile.memory_usage_mb:.0f}MB memory",
                expected_improvement="30-50% memory reduction",
                implementation_effort="medium",
                code_changes=[
                    "Implement object pooling for large objects",
                    "Use streaming for large data processing",
                    "Optimize data structures and reduce copying"
                ]
            ))
        
        return recommendations
    
    def _convert_cache_recommendation(self, cache_rec: Dict[str, Any]) -> OptimizationRecommendation:
        """Convert cache analysis recommendation to optimization recommendation."""
        severity_to_priority = {"high": "high", "medium": "medium", "low": "low"}
        
        return OptimizationRecommendation(
            category="caching",
            priority=severity_to_priority.get(cache_rec["severity"], "low"),
            description=cache_rec["message"],
            expected_improvement="10-30% performance improvement",
            implementation_effort="low",
            code_changes=cache_rec.get("suggestions", [])
        )
    
    def optimize_cache_configuration(self) -> Dict[str, Any]:
        """Analyze and optimize cache configuration."""
        try:
            # Get current cache statistics
            cache_stats = self.cache_service.get_cache_stats()
            
            optimization_results = {
                "current_config": {
                    "ttl_seconds": getattr(self.config, 'cache_ttl', 3600),
                    "max_memory": getattr(self.config, 'redis_max_memory', 'unknown'),
                    "eviction_policy": "unknown"  # Would need Redis config access
                },
                "analysis": cache_stats,
                "recommendations": {}
            }
            
            # Analyze hit ratio and suggest TTL optimization
            hit_ratio = cache_stats.get("hit_ratio", 0.0)
            if hit_ratio < 0.4:
                optimization_results["recommendations"]["ttl"] = {
                    "current": getattr(self.config, 'cache_ttl', 3600),
                    "recommended": 7200,  # Increase TTL
                    "reason": "Low hit ratio suggests data is expiring too quickly"
                }
            elif hit_ratio > 0.8:
                optimization_results["recommendations"]["ttl"] = {
                    "current": getattr(self.config, 'cache_ttl', 3600),
                    "recommended": 1800,  # Decrease TTL
                    "reason": "High hit ratio allows for shorter TTL to keep data fresh"
                }
            
            # Memory optimization
            memory_usage = cache_stats.get("memory_usage", 0)
            if memory_usage > 50 * 1024 * 1024:  # 50MB
                optimization_results["recommendations"]["memory"] = {
                    "current_usage_mb": memory_usage / 1024 / 1024,
                    "suggestions": [
                        "Implement cache compression",
                        "Use more selective caching",
                        "Implement cache size limits"
                    ]
                }
            
            return optimization_results
            
        except Exception as e:
            return {
                "error": f"Cache optimization failed: {str(e)}",
                "recommendations": {
                    "fallback": "Check Redis connectivity and configuration"
                }
            }
    
    def benchmark_cache_strategies(self) -> Dict[str, Any]:
        """Benchmark different caching strategies."""
        strategies = {
            "no_cache": {"ttl": 0, "description": "No caching"},
            "short_ttl": {"ttl": 300, "description": "5 minute TTL"},
            "medium_ttl": {"ttl": 1800, "description": "30 minute TTL"},
            "long_ttl": {"ttl": 7200, "description": "2 hour TTL"}
        }
        
        results = {}
        
        # Simulate different cache scenarios
        for strategy_name, config in strategies.items():
            # This would require actual load testing to be meaningful
            # For now, provide theoretical analysis
            results[strategy_name] = {
                "config": config,
                "estimated_hit_ratio": self._estimate_hit_ratio(config["ttl"]),
                "estimated_response_time_ms": self._estimate_response_time(config["ttl"]),
                "pros": self._get_strategy_pros(config["ttl"]),
                "cons": self._get_strategy_cons(config["ttl"])
            }
        
        # Recommend best strategy
        best_strategy = max(results.keys(), 
                          key=lambda k: results[k]["estimated_hit_ratio"] * 0.7 + 
                                      (1000 / max(results[k]["estimated_response_time_ms"], 100)) * 0.3)
        
        results["recommendation"] = {
            "best_strategy": best_strategy,
            "reason": f"Optimal balance of hit ratio and response time",
            "config": strategies[best_strategy]
        }
        
        return results
    
    def _estimate_hit_ratio(self, ttl_seconds: int) -> float:
        """Estimate cache hit ratio based on TTL."""
        if ttl_seconds == 0:
            return 0.0
        elif ttl_seconds < 600:  # 10 minutes
            return 0.3
        elif ttl_seconds < 3600:  # 1 hour
            return 0.6
        else:
            return 0.8
    
    def _estimate_response_time(self, ttl_seconds: int) -> float:
        """Estimate response time based on caching strategy."""
        base_time = 500  # Base response time without cache
        cache_time = 50   # Cache hit response time
        
        hit_ratio = self._estimate_hit_ratio(ttl_seconds)
        return (hit_ratio * cache_time) + ((1 - hit_ratio) * base_time)
    
    def _get_strategy_pros(self, ttl_seconds: int) -> List[str]:
        """Get pros for a caching strategy."""
        if ttl_seconds == 0:
            return ["Always fresh data", "No stale data issues"]
        elif ttl_seconds < 600:
            return ["Relatively fresh data", "Low memory usage"]
        elif ttl_seconds < 3600:
            return ["Good balance of freshness and performance", "Moderate memory usage"]
        else:
            return ["High performance", "Reduced external API calls"]
    
    def _get_strategy_cons(self, ttl_seconds: int) -> List[str]:
        """Get cons for a caching strategy."""
        if ttl_seconds == 0:
            return ["No performance benefit", "High external API load"]
        elif ttl_seconds < 600:
            return ["Frequent cache misses", "Moderate external API load"]
        elif ttl_seconds < 3600:
            return ["Some stale data possible", "Moderate memory usage"]
        else:
            return ["Potentially stale data", "High memory usage"]
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_operations_analyzed": len(self.performance_data),
                "cache_analysis": self.analyze_cache_performance(),
                "optimization_recommendations": len(self.generate_optimization_recommendations())
            },
            "operation_profiles": {
                name: {
                    "mean_time_ms": profile.mean_time_ms,
                    "p95_time_ms": profile.p95_time_ms,
                    "success_rate": profile.success_rate,
                    "cache_hit_rate": profile.cache_hit_rate,
                    "sample_count": profile.sample_count
                }
                for name, profile in self.performance_data.items()
            },
            "recommendations": [
                {
                    "category": rec.category,
                    "priority": rec.priority,
                    "description": rec.description,
                    "expected_improvement": rec.expected_improvement,
                    "implementation_effort": rec.implementation_effort,
                    "code_changes": rec.code_changes
                }
                for rec in self.generate_optimization_recommendations()
            ],
            "cache_optimization": self.optimize_cache_configuration(),
            "cache_strategy_analysis": self.benchmark_cache_strategies()
        }
        
        return report
    
    def save_report(self, report: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Save performance report to file."""
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        return filename


def run_performance_analysis():
    """Run comprehensive performance analysis."""
    analyzer = PerformanceAnalyzer()
    
    print("Terra Pulse-Dify Integration Performance Analysis")
    print("=" * 50)
    
    # Example usage - in real scenario, this would collect actual metrics
    # For demonstration, using simulated data
    
    # Simulate Terra Pulse performance data
    terra_pulse_times = [120, 135, 98, 156, 142, 108, 167, 134, 145, 129]
    analyzer.collect_performance_metrics(
        "terra_pulse_prediction",
        terra_pulse_times,
        success_count=10,
        total_count=10,
        cache_hits=3,
        cache_total=10,
        memory_usage=45.2
    )
    
    # Simulate Dify workflow performance data
    dify_times = [1200, 1450, 980, 1650, 1320, 1180, 1890, 1340, 1520, 1290]
    analyzer.collect_performance_metrics(
        "dify_workflow_execution",
        dify_times,
        success_count=9,
        total_count=10,
        cache_hits=1,
        cache_total=10,
        memory_usage=78.5
    )
    
    # Generate and display report
    report = analyzer.generate_performance_report()
    
    print(f"Analysis completed at: {report['timestamp']}")
    print(f"Operations analyzed: {report['summary']['total_operations_analyzed']}")
    print(f"Recommendations generated: {report['summary']['optimization_recommendations']}")
    
    print("\nTop Recommendations:")
    for i, rec in enumerate(report['recommendations'][:3], 1):
        print(f"{i}. [{rec['priority'].upper()}] {rec['description']}")
        print(f"   Expected improvement: {rec['expected_improvement']}")
        print(f"   Implementation effort: {rec['implementation_effort']}")
    
    # Save report
    filename = analyzer.save_report(report)
    print(f"\nFull report saved to: {filename}")
    
    return report


if __name__ == "__main__":
    run_performance_analysis()