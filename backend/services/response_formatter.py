"""
Response formatting utilities for different user types and localization.
Handles farmer vs official formatting and regional adaptations.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class UserType(Enum):
    """User type enumeration."""
    FARMER = "farmer"
    OFFICIAL = "official"


class Region(Enum):
    """Supported regions for localization."""
    EAST_AFRICA = "east_africa"
    WEST_AFRICA = "west_africa"
    SOUTHERN_AFRICA = "southern_africa"
    GENERAL = "general"


@dataclass
class MessageTemplate:
    """Template for formatted messages."""
    title: str
    summary: str
    recommendations: List[str]
    urgency_level: str
    technical_details: Optional[str] = None
    policy_recommendations: Optional[List[str]] = None


class ResponseFormatter:
    """
    Response formatter for different user types and regions.
    Provides user-specific formatting and localization support.
    """
    
    def __init__(self):
        """Initialize response formatter."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._load_templates()
    
    def _load_templates(self):
        """Load message templates for different user types and regions."""
        # Risk level thresholds
        self.risk_thresholds = {
            'critical': 80,
            'high': 60,
            'moderate': 30,
            'low': 0
        }
        
        # Action urgency mapping
        self.urgency_mapping = {
            'critical': 'immediate',
            'high': 'urgent',
            'moderate': 'planned',
            'low': 'monitoring'
        }
        
        # Regional crop and practice adaptations
        self.regional_adaptations = {
            Region.EAST_AFRICA: {
                'common_crops': ['maize', 'sorghum', 'millet', 'beans'],
                'climate_context': 'semi-arid conditions with irregular rainfall',
                'local_practices': ['terracing', 'agroforestry', 'water harvesting'],
                'currency': 'KES/USD',
                'measurement': 'hectares'
            },
            Region.WEST_AFRICA: {
                'common_crops': ['millet', 'sorghum', 'cowpeas', 'groundnuts'],
                'climate_context': 'Sahel conditions with seasonal rainfall',
                'local_practices': ['contour farming', 'crop rotation', 'composting'],
                'currency': 'CFA/USD',
                'measurement': 'hectares'
            },
            Region.SOUTHERN_AFRICA: {
                'common_crops': ['maize', 'sorghum', 'cassava', 'sweet potato'],
                'climate_context': 'variable rainfall with drought risk',
                'local_practices': ['conservation agriculture', 'mulching', 'intercropping'],
                'currency': 'ZAR/USD',
                'measurement': 'hectares'
            },
            Region.GENERAL: {
                'common_crops': ['crops'],
                'climate_context': 'local climate conditions',
                'local_practices': ['sustainable farming practices'],
                'currency': 'local currency',
                'measurement': 'land area'
            }
        }
    
    def _determine_risk_level(self, degradation_risk: int) -> str:
        """
        Determine risk level category from degradation risk percentage.
        
        Args:
            degradation_risk: Risk percentage (0-100)
            
        Returns:
            str: Risk level category
        """
        if degradation_risk >= self.risk_thresholds['critical']:
            return 'critical'
        elif degradation_risk >= self.risk_thresholds['high']:
            return 'high'
        elif degradation_risk >= self.risk_thresholds['moderate']:
            return 'moderate'
        else:
            return 'low'
    
    def _detect_region(self, location: str) -> Region:
        """
        Detect region from location string for localization.
        
        Args:
            location: Location string
            
        Returns:
            Region: Detected region
        """
        location_lower = location.lower()
        
        # East Africa keywords
        east_africa_keywords = [
            'kenya', 'uganda', 'tanzania', 'ethiopia', 'rwanda', 'burundi',
            'baringo', 'turkana', 'karamoja', 'somali', 'afar'
        ]
        
        # West Africa keywords
        west_africa_keywords = [
            'mali', 'burkina faso', 'niger', 'senegal', 'mauritania', 'chad',
            'sahel', 'sudan', 'gambia'
        ]
        
        # Southern Africa keywords
        southern_africa_keywords = [
            'south africa', 'botswana', 'namibia', 'zimbabwe', 'zambia',
            'lesotho', 'swaziland', 'mozambique'
        ]
        
        for keyword in east_africa_keywords:
            if keyword in location_lower:
                return Region.EAST_AFRICA
        
        for keyword in west_africa_keywords:
            if keyword in location_lower:
                return Region.WEST_AFRICA
        
        for keyword in southern_africa_keywords:
            if keyword in location_lower:
                return Region.SOUTHERN_AFRICA
        
        return Region.GENERAL
    
    def _format_farmer_message(self, merged_response: Dict[str, Any], 
                             region: Region, risk_level: str) -> MessageTemplate:
        """
        Format message for farmer users with practical, actionable language.
        
        Args:
            merged_response: Merged Terra Pulse and Dify response
            region: Detected region for localization
            risk_level: Risk level category
            
        Returns:
            MessageTemplate: Formatted message template
        """
        terra_pred = merged_response.get('terra_pulse_prediction', {})
        ai_insights = merged_response.get('ai_insights', {})
        
        degradation_risk = terra_pred.get('degradation_risk', 0)
        location = terra_pred.get('location', 'your area')
        confidence = terra_pred.get('confidence', 0.0)
        
        regional_info = self.regional_adaptations[region]
        
        # Create title based on risk level
        risk_titles = {
            'critical': f"🚨 Urgent: High soil degradation risk in {location}",
            'high': f"⚠️ Warning: Soil degradation detected in {location}",
            'moderate': f"📊 Notice: Moderate soil risk in {location}",
            'low': f"✅ Good news: Soil health looks stable in {location}"
        }
        
        title = risk_titles.get(risk_level, f"Soil assessment for {location}")
        
        # Create summary with practical language
        if risk_level == 'critical':
            summary = (f"Your land shows {degradation_risk}% degradation risk. "
                      f"Immediate action needed to protect your soil and crops. "
                      f"This affects your {regional_info['common_crops'][0]} and other crops.")
        elif risk_level == 'high':
            summary = (f"Your land has {degradation_risk}% degradation risk. "
                      f"Take action soon to prevent soil loss and maintain crop yields.")
        elif risk_level == 'moderate':
            summary = (f"Your land shows {degradation_risk}% degradation risk. "
                      f"Some preventive measures will help maintain soil health.")
        else:
            summary = (f"Your land shows low degradation risk ({degradation_risk}%). "
                      f"Continue your current good practices.")
        
        # Format recommendations in practical terms
        ai_recommendations = ai_insights.get('enhanced_recommendations', [])
        practical_recommendations = []
        
        for rec in ai_recommendations:
            # Simplify technical language
            simplified = rec.lower()
            if 'mulch' in simplified or 'residue' in simplified:
                practical_recommendations.append(
                    f"Cover bare soil with crop residue or grass to prevent erosion"
                )
            elif 'contour' in simplified:
                practical_recommendations.append(
                    f"Plant across slopes (contour farming) to slow water runoff"
                )
            elif 'cover crop' in simplified:
                practical_recommendations.append(
                    f"Plant cover crops between seasons to protect soil"
                )
            elif 'water' in simplified and 'conserv' in simplified:
                practical_recommendations.append(
                    f"Dig small trenches or bunds to catch and hold rainwater"
                )
            else:
                practical_recommendations.append(rec)
        
        # Add region-specific recommendations if AI recommendations are limited
        if len(practical_recommendations) < 2:
            if risk_level in ['critical', 'high']:
                practical_recommendations.extend([
                    f"Apply {regional_info['local_practices'][0]} techniques immediately",
                    f"Use available materials to cover exposed soil",
                    f"Consider drought-resistant {regional_info['common_crops'][0]} varieties"
                ])
        
        # Determine urgency
        urgency_level = self.urgency_mapping.get(risk_level, 'monitoring')
        
        return MessageTemplate(
            title=title,
            summary=summary,
            recommendations=practical_recommendations[:5],  # Limit to 5 key recommendations
            urgency_level=urgency_level,
            technical_details=None  # Farmers don't need technical details
        )
    
    def _format_official_message(self, merged_response: Dict[str, Any], 
                               region: Region, risk_level: str) -> MessageTemplate:
        """
        Format message for official users with technical details and policy recommendations.
        
        Args:
            merged_response: Merged Terra Pulse and Dify response
            region: Detected region for localization
            risk_level: Risk level category
            
        Returns:
            MessageTemplate: Formatted message template
        """
        terra_pred = merged_response.get('terra_pulse_prediction', {})
        ai_insights = merged_response.get('ai_insights', {})
        metadata = merged_response.get('metadata', {})
        
        degradation_risk = terra_pred.get('degradation_risk', 0)
        location = terra_pred.get('location', 'assessed area')
        confidence = terra_pred.get('confidence', 0.0)
        risk_factors = terra_pred.get('risk_factors', [])
        
        regional_info = self.regional_adaptations[region]
        
        # Create technical title
        title = f"Land Degradation Assessment: {location} - {risk_level.upper()} Risk ({degradation_risk}%)"
        
        # Create technical summary
        summary = (f"Satellite-based analysis indicates {degradation_risk}% degradation risk "
                  f"in {location} with {confidence:.1%} confidence. "
                  f"Primary risk factors: {', '.join(risk_factors)}. "
                  f"Assessment based on NDVI analysis under {regional_info['climate_context']}.")
        
        # Format technical recommendations
        ai_recommendations = ai_insights.get('enhanced_recommendations', [])
        technical_recommendations = []
        
        for rec in ai_recommendations:
            # Keep technical language for officials
            technical_recommendations.append(rec)
        
        # Add policy-level recommendations
        policy_recommendations = []
        
        if risk_level == 'critical':
            policy_recommendations.extend([
                f"Deploy emergency soil conservation programs in {location}",
                f"Coordinate with local extension services for immediate farmer support",
                f"Consider subsidized {regional_info['local_practices'][0]} implementation",
                f"Activate drought response protocols if applicable"
            ])
        elif risk_level == 'high':
            policy_recommendations.extend([
                f"Implement targeted conservation programs in {location}",
                f"Provide technical assistance for sustainable land management",
                f"Monitor degradation trends with follow-up assessments",
                f"Support farmer training on {regional_info['local_practices'][1]}"
            ])
        elif risk_level == 'moderate':
            policy_recommendations.extend([
                f"Establish preventive conservation measures in {location}",
                f"Promote sustainable agricultural practices",
                f"Continue regular monitoring and early warning systems"
            ])
        else:
            policy_recommendations.extend([
                f"Maintain current conservation programs in {location}",
                f"Use as model area for best practices documentation",
                f"Continue routine monitoring"
            ])
        
        # Create technical details
        technical_details = (
            f"Model confidence: {confidence:.1%} | "
            f"Processing time: {metadata.get('processing_time', 0):.1f}ms | "
            f"Risk factors: {len(risk_factors)} identified | "
            f"AI enhancement: {'Available' if metadata.get('ai_enhancement_available') else 'Fallback used'}"
        )
        
        urgency_level = self.urgency_mapping.get(risk_level, 'monitoring')
        
        return MessageTemplate(
            title=title,
            summary=summary,
            recommendations=technical_recommendations,
            urgency_level=urgency_level,
            technical_details=technical_details,
            policy_recommendations=policy_recommendations
        )
    
    def format_response_for_user(self, merged_response: Dict[str, Any], 
                               user_type: str, location_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Format merged response for specific user type with localization.
        
        Args:
            merged_response: Merged Terra Pulse and Dify response
            user_type: Type of user ('farmer' or 'official')
            location_override: Optional location override for region detection
            
        Returns:
            Dict[str, Any]: Formatted response with user-specific messaging
        """
        try:
            # Determine user type and normalize
            user_type_normalized = user_type.lower()
            user_enum = UserType.FARMER if user_type_normalized == 'farmer' else UserType.OFFICIAL
            
            # Get location for region detection
            terra_pred = merged_response.get('terra_pulse_prediction', {})
            location = location_override or terra_pred.get('location', 'Unknown')
            
            # Detect region for localization
            region = self._detect_region(location)
            
            # Determine risk level
            degradation_risk = terra_pred.get('degradation_risk', 0)
            risk_level = self._determine_risk_level(degradation_risk)
            
            # Format message based on user type
            if user_enum == UserType.FARMER:
                message_template = self._format_farmer_message(merged_response, region, risk_level)
            else:
                message_template = self._format_official_message(merged_response, region, risk_level)
            
            # Create formatted response
            formatted_response = {
                'user_type': user_type_normalized,
                'region': region.value,
                'risk_level': risk_level,
                'urgency': message_template.urgency_level,
                'title': message_template.title,
                'summary': message_template.summary,
                'recommendations': message_template.recommendations,
                'technical_details': message_template.technical_details,
                'policy_recommendations': message_template.policy_recommendations
            }
            
            # Add the formatted response to the merged response
            enhanced_response = merged_response.copy()
            enhanced_response['formatted_response'] = formatted_response
            
            # Add user-friendly message for quick consumption
            if user_enum == UserType.FARMER:
                enhanced_response['formatted_response']['farmer_message'] = (
                    f"{message_template.summary} "
                    f"Key action: {message_template.recommendations[0] if message_template.recommendations else 'Monitor soil health'}"
                )
            else:
                enhanced_response['formatted_response']['official_summary'] = (
                    f"Risk Level: {risk_level.upper()} ({degradation_risk}%) | "
                    f"Confidence: {terra_pred.get('confidence', 0):.1%} | "
                    f"Action Required: {message_template.urgency_level}"
                )
            
            self.logger.info(f"Successfully formatted response for {user_type} in {region.value}")
            return enhanced_response
            
        except Exception as e:
            self.logger.error(f"Failed to format response for user type {user_type}: {str(e)}")
            
            # Return basic fallback response when original response is invalid
            if merged_response is None:
                fallback_response = {}
                terra_pred = {}
            else:
                fallback_response = merged_response.copy()
                terra_pred = merged_response.get('terra_pulse_prediction', {})
            
            fallback_response['formatted_response'] = {
                'user_type': user_type.lower(),
                'region': 'general',
                'risk_level': 'unknown',
                'urgency': 'review',
                'title': f"Land Assessment for {terra_pred.get('location', 'your area')}",
                'summary': f"Degradation risk: {terra_pred.get('degradation_risk', 0)}%",
                'recommendations': ['Review detailed assessment results'],
                'technical_details': None,
                'policy_recommendations': None,
                'error': f"Formatting failed: {str(e)}"
            }
            
            return fallback_response
    
    def create_multi_language_response(self, formatted_response: Dict[str, Any], 
                                     languages: List[str] = None) -> Dict[str, Any]:
        """
        Create multi-language version of formatted response.
        Currently supports basic English adaptations for different regions.
        
        Args:
            formatted_response: Already formatted response
            languages: List of language codes (future enhancement)
            
        Returns:
            Dict[str, Any]: Multi-language response
        """
        # This is a placeholder for future multi-language support
        # Currently returns the original response with language metadata
        
        multi_lang_response = formatted_response.copy()
        multi_lang_response['language_info'] = {
            'primary_language': 'en',
            'supported_languages': ['en'],
            'regional_adaptation': formatted_response.get('formatted_response', {}).get('region', 'general')
        }
        
        return multi_lang_response
    
    def get_formatting_metrics(self, formatted_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metrics from formatted response for monitoring.
        
        Args:
            formatted_response: Formatted response
            
        Returns:
            Dict[str, Any]: Formatting metrics
        """
        try:
            formatted_data = formatted_response.get('formatted_response', {})
            
            metrics = {
                'user_type': formatted_data.get('user_type', 'unknown'),
                'region': formatted_data.get('region', 'unknown'),
                'risk_level': formatted_data.get('risk_level', 'unknown'),
                'urgency': formatted_data.get('urgency', 'unknown'),
                'recommendations_count': len(formatted_data.get('recommendations', [])),
                'has_technical_details': formatted_data.get('technical_details') is not None,
                'has_policy_recommendations': formatted_data.get('policy_recommendations') is not None,
                'formatting_success': 'error' not in formatted_data
            }
            
            return metrics
            
        except Exception as e:
            return {
                'error': str(e),
                'formatting_success': False
            }