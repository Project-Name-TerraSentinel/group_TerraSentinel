"""
Unit tests for response formatting utilities.
Tests user-specific formatting and regional adaptations.
"""

import pytest
from unittest.mock import Mock, patch

from backend.services.response_formatter import (
    ResponseFormatter, UserType, Region, MessageTemplate
)


class TestResponseFormatter:
    """Test suite for ResponseFormatter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ResponseFormatter()
        
        # Sample merged response
        self.sample_merged_response = {
            'terra_pulse_prediction': {
                'location': 'Baringo County, Kenya',
                'degradation_risk': 75,
                'risk_factors': ['bare_soil_increase', 'low_ndvi'],
                'recommended_action_key': 'mulch_crop_residue',
                'confidence': 0.85,
                'user_context': 'smallholder_farmer'
            },
            'ai_insights': {
                'enhanced_recommendations': [
                    'Apply crop residue mulch within 2 weeks',
                    'Consider drought-resistant maize varieties',
                    'Implement contour farming on slopes'
                ],
                'risk_assessment': 'High degradation risk due to recent drought conditions',
                'timeline': 'Immediate action required within 14 days',
                'cost_estimate': 'Low cost - use existing crop residue',
                'success_probability': 0.78,
                'additional_insights': {'climate_factor': 'drought_stress'}
            },
            'metadata': {
                'processing_time': 122.8,
                'dify_workflow_id': 'workflow_123',
                'dify_status': 'success',
                'ai_enhancement_available': True,
                'timestamp': '2024-01-01T00:00:00Z'
            }
        }


class TestRiskLevelDetermination:
    """Test risk level determination functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ResponseFormatter()
    
    def test_determine_risk_level_critical(self):
        """Test critical risk level determination."""
        risk_level = self.formatter._determine_risk_level(85)
        assert risk_level == 'critical'
    
    def test_determine_risk_level_high(self):
        """Test high risk level determination."""
        risk_level = self.formatter._determine_risk_level(70)
        assert risk_level == 'high'
    
    def test_determine_risk_level_moderate(self):
        """Test moderate risk level determination."""
        risk_level = self.formatter._determine_risk_level(45)
        assert risk_level == 'moderate'
    
    def test_determine_risk_level_low(self):
        """Test low risk level determination."""
        risk_level = self.formatter._determine_risk_level(15)
        assert risk_level == 'low'
    
    def test_determine_risk_level_boundary_values(self):
        """Test boundary values for risk levels."""
        assert self.formatter._determine_risk_level(80) == 'critical'
        assert self.formatter._determine_risk_level(79) == 'high'
        assert self.formatter._determine_risk_level(60) == 'high'
        assert self.formatter._determine_risk_level(59) == 'moderate'
        assert self.formatter._determine_risk_level(30) == 'moderate'
        assert self.formatter._determine_risk_level(29) == 'low'


class TestRegionDetection:
    """Test region detection functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ResponseFormatter()
    
    def test_detect_region_east_africa(self):
        """Test East Africa region detection."""
        locations = [
            'Baringo County, Kenya',
            'Kampala, Uganda',
            'Arusha, Tanzania',
            'Addis Ababa, Ethiopia',
            'Kigali, Rwanda'
        ]
        
        for location in locations:
            region = self.formatter._detect_region(location)
            assert region == Region.EAST_AFRICA
    
    def test_detect_region_west_africa(self):
        """Test West Africa region detection."""
        locations = [
            'Bamako, Mali',
            'Ouagadougou, Burkina Faso',
            'Niamey, Niger',
            'Dakar, Senegal',
            'Sahel region'
        ]
        
        for location in locations:
            region = self.formatter._detect_region(location)
            assert region == Region.WEST_AFRICA
    
    def test_detect_region_southern_africa(self):
        """Test Southern Africa region detection."""
        locations = [
            'Cape Town, South Africa',
            'Gaborone, Botswana',
            'Windhoek, Namibia',
            'Harare, Zimbabwe',
            'Lusaka, Zambia'
        ]
        
        for location in locations:
            region = self.formatter._detect_region(location)
            assert region == Region.SOUTHERN_AFRICA
    
    def test_detect_region_general(self):
        """Test general region detection for unknown locations."""
        locations = [
            'Unknown Location',
            'Some Random Place',
            'Test Location'
        ]
        
        for location in locations:
            region = self.formatter._detect_region(location)
            assert region == Region.GENERAL
    
    def test_detect_region_case_insensitive(self):
        """Test case-insensitive region detection."""
        locations = [
            'KENYA',
            'kenya',
            'Kenya',
            'BARINGO COUNTY, KENYA'
        ]
        
        for location in locations:
            region = self.formatter._detect_region(location)
            assert region == Region.EAST_AFRICA


class TestFarmerMessageFormatting:
    """Test farmer-specific message formatting."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ResponseFormatter()
        
        self.sample_response = {
            'terra_pulse_prediction': {
                'location': 'Baringo County, Kenya',
                'degradation_risk': 75,
                'risk_factors': ['bare_soil_increase', 'low_ndvi'],
                'confidence': 0.85
            },
            'ai_insights': {
                'enhanced_recommendations': [
                    'Apply crop residue mulch within 2 weeks',
                    'Consider drought-resistant maize varieties',
                    'Implement contour farming on slopes'
                ]
            },
            'metadata': {}
        }
    
    def test_format_farmer_message_critical_risk(self):
        """Test farmer message formatting for critical risk."""
        self.sample_response['terra_pulse_prediction']['degradation_risk'] = 85
        
        template = self.formatter._format_farmer_message(
            self.sample_response, 
            Region.EAST_AFRICA, 
            'critical'
        )
        
        assert isinstance(template, MessageTemplate)
        assert '🚨 Urgent' in template.title
        assert 'Immediate action needed' in template.summary
        assert template.urgency_level == 'immediate'
        assert len(template.recommendations) > 0
        assert template.technical_details is None  # Farmers don't get technical details
    
    def test_format_farmer_message_high_risk(self):
        """Test farmer message formatting for high risk."""
        template = self.formatter._format_farmer_message(
            self.sample_response, 
            Region.EAST_AFRICA, 
            'high'
        )
        
        assert '⚠️ Warning' in template.title
        assert 'Take action soon' in template.summary
        assert template.urgency_level == 'urgent'
    
    def test_format_farmer_message_moderate_risk(self):
        """Test farmer message formatting for moderate risk."""
        self.sample_response['terra_pulse_prediction']['degradation_risk'] = 45
        
        template = self.formatter._format_farmer_message(
            self.sample_response, 
            Region.EAST_AFRICA, 
            'moderate'
        )
        
        assert '📊 Notice' in template.title
        assert 'preventive measures' in template.summary
        assert template.urgency_level == 'planned'
    
    def test_format_farmer_message_low_risk(self):
        """Test farmer message formatting for low risk."""
        self.sample_response['terra_pulse_prediction']['degradation_risk'] = 15
        
        template = self.formatter._format_farmer_message(
            self.sample_response, 
            Region.EAST_AFRICA, 
            'low'
        )
        
        assert '✅ Good news' in template.title
        assert 'low degradation risk' in template.summary
        assert template.urgency_level == 'monitoring'
    
    def test_format_farmer_message_practical_recommendations(self):
        """Test that farmer recommendations are practical and simplified."""
        template = self.formatter._format_farmer_message(
            self.sample_response, 
            Region.EAST_AFRICA, 
            'high'
        )
        
        # Check that recommendations are simplified
        for rec in template.recommendations:
            assert isinstance(rec, str)
            assert len(rec) > 0
            # Should not contain overly technical language
            assert 'NDVI' not in rec
            assert 'algorithm' not in rec
    
    def test_format_farmer_message_regional_adaptation(self):
        """Test regional adaptation in farmer messages."""
        # Test East Africa
        template_ea = self.formatter._format_farmer_message(
            self.sample_response, 
            Region.EAST_AFRICA, 
            'high'
        )
        
        # Should mention regional crops
        summary_and_recs = template_ea.summary + ' '.join(template_ea.recommendations)
        assert any(crop in summary_and_recs for crop in ['maize', 'sorghum', 'millet'])
        
        # Test West Africa
        template_wa = self.formatter._format_farmer_message(
            self.sample_response, 
            Region.WEST_AFRICA, 
            'high'
        )
        
        # Should adapt to West African context
        assert isinstance(template_wa, MessageTemplate)


class TestOfficialMessageFormatting:
    """Test official-specific message formatting."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ResponseFormatter()
        
        self.sample_response = {
            'terra_pulse_prediction': {
                'location': 'Baringo County, Kenya',
                'degradation_risk': 75,
                'risk_factors': ['bare_soil_increase', 'low_ndvi'],
                'confidence': 0.85
            },
            'ai_insights': {
                'enhanced_recommendations': [
                    'Deploy emergency soil conservation programs',
                    'Coordinate with local extension services',
                    'Implement policy interventions'
                ]
            },
            'metadata': {
                'processing_time': 122.8,
                'ai_enhancement_available': True
            }
        }
    
    def test_format_official_message_critical_risk(self):
        """Test official message formatting for critical risk."""
        self.sample_response['terra_pulse_prediction']['degradation_risk'] = 85
        
        template = self.formatter._format_official_message(
            self.sample_response, 
            Region.EAST_AFRICA, 
            'critical'
        )
        
        assert isinstance(template, MessageTemplate)
        assert 'Land Degradation Assessment' in template.title
        assert 'CRITICAL Risk' in template.title
        assert 'Satellite-based analysis' in template.summary
        assert template.technical_details is not None
        assert template.policy_recommendations is not None
        assert len(template.policy_recommendations) > 0
    
    def test_format_official_message_technical_details(self):
        """Test that official messages include technical details."""
        template = self.formatter._format_official_message(
            self.sample_response, 
            Region.EAST_AFRICA, 
            'high'
        )
        
        assert template.technical_details is not None
        assert 'confidence' in template.technical_details.lower()
        assert 'processing time' in template.technical_details.lower()
    
    def test_format_official_message_policy_recommendations(self):
        """Test policy recommendations for officials."""
        template = self.formatter._format_official_message(
            self.sample_response, 
            Region.EAST_AFRICA, 
            'critical'
        )
        
        assert template.policy_recommendations is not None
        assert len(template.policy_recommendations) > 0
        
        # Should contain policy-level language
        policy_text = ' '.join(template.policy_recommendations)
        assert any(word in policy_text.lower() for word in ['deploy', 'coordinate', 'implement', 'program'])
    
    def test_format_official_message_different_risk_levels(self):
        """Test official messages for different risk levels."""
        risk_levels = ['critical', 'high', 'moderate', 'low']
        
        for risk_level in risk_levels:
            template = self.formatter._format_official_message(
                self.sample_response, 
                Region.EAST_AFRICA, 
                risk_level
            )
            
            assert isinstance(template, MessageTemplate)
            assert template.policy_recommendations is not None
            assert len(template.policy_recommendations) > 0


class TestResponseFormattingIntegration:
    """Test complete response formatting workflow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ResponseFormatter()
        
        self.sample_merged_response = {
            'terra_pulse_prediction': {
                'location': 'Baringo County, Kenya',
                'degradation_risk': 75,
                'risk_factors': ['bare_soil_increase', 'low_ndvi'],
                'recommended_action_key': 'mulch_crop_residue',
                'confidence': 0.85,
                'user_context': 'smallholder_farmer'
            },
            'ai_insights': {
                'enhanced_recommendations': [
                    'Apply crop residue mulch within 2 weeks',
                    'Consider drought-resistant maize varieties',
                    'Implement contour farming on slopes'
                ],
                'risk_assessment': 'High degradation risk due to recent drought conditions',
                'timeline': 'Immediate action required within 14 days',
                'cost_estimate': 'Low cost - use existing crop residue',
                'success_probability': 0.78,
                'additional_insights': {'climate_factor': 'drought_stress'}
            },
            'metadata': {
                'processing_time': 122.8,
                'dify_workflow_id': 'workflow_123',
                'dify_status': 'success',
                'ai_enhancement_available': True,
                'timestamp': '2024-01-01T00:00:00Z'
            }
        }
    
    def test_format_response_for_farmer(self):
        """Test complete response formatting for farmer."""
        formatted = self.formatter.format_response_for_user(
            self.sample_merged_response, 
            'farmer'
        )
        
        assert 'formatted_response' in formatted
        formatted_resp = formatted['formatted_response']
        
        assert formatted_resp['user_type'] == 'farmer'
        assert formatted_resp['region'] == 'east_africa'
        assert formatted_resp['risk_level'] == 'high'
        assert formatted_resp['urgency'] == 'urgent'
        assert 'title' in formatted_resp
        assert 'summary' in formatted_resp
        assert 'recommendations' in formatted_resp
        assert formatted_resp['technical_details'] is None
        assert 'farmer_message' in formatted_resp
    
    def test_format_response_for_official(self):
        """Test complete response formatting for official."""
        formatted = self.formatter.format_response_for_user(
            self.sample_merged_response, 
            'official'
        )
        
        assert 'formatted_response' in formatted
        formatted_resp = formatted['formatted_response']
        
        assert formatted_resp['user_type'] == 'official'
        assert formatted_resp['region'] == 'east_africa'
        assert formatted_resp['risk_level'] == 'high'
        assert formatted_resp['technical_details'] is not None
        assert formatted_resp['policy_recommendations'] is not None
        assert 'official_summary' in formatted_resp
    
    def test_format_response_location_override(self):
        """Test response formatting with location override."""
        formatted = self.formatter.format_response_for_user(
            self.sample_merged_response, 
            'farmer',
            location_override='Bamako, Mali'
        )
        
        formatted_resp = formatted['formatted_response']
        assert formatted_resp['region'] == 'west_africa'
    
    def test_format_response_different_regions(self):
        """Test response formatting for different regions."""
        regions_and_locations = [
            ('east_africa', 'Nairobi, Kenya'),
            ('west_africa', 'Bamako, Mali'),
            ('southern_africa', 'Cape Town, South Africa'),
            ('general', 'Unknown Location')
        ]
        
        for expected_region, location in regions_and_locations:
            formatted = self.formatter.format_response_for_user(
                self.sample_merged_response, 
                'farmer',
                location_override=location
            )
            
            assert formatted['formatted_response']['region'] == expected_region
    
    def test_format_response_error_handling(self):
        """Test response formatting error handling."""
        # Test with None response that will cause an exception
        invalid_response = None
        
        formatted = self.formatter.format_response_for_user(
            invalid_response, 
            'farmer'
        )
        
        # Should return fallback response
        assert 'formatted_response' in formatted
        assert 'error' in formatted['formatted_response']
    
    def test_format_response_case_insensitive_user_type(self):
        """Test case-insensitive user type handling."""
        user_types = ['FARMER', 'farmer', 'Farmer', 'OFFICIAL', 'official', 'Official']
        
        for user_type in user_types:
            formatted = self.formatter.format_response_for_user(
                self.sample_merged_response, 
                user_type
            )
            
            expected_type = 'farmer' if user_type.lower() == 'farmer' else 'official'
            assert formatted['formatted_response']['user_type'] == expected_type


class TestMultiLanguageSupport:
    """Test multi-language support functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ResponseFormatter()
        
        self.sample_formatted_response = {
            'formatted_response': {
                'user_type': 'farmer',
                'region': 'east_africa',
                'risk_level': 'high'
            }
        }
    
    def test_create_multi_language_response(self):
        """Test multi-language response creation."""
        multi_lang = self.formatter.create_multi_language_response(
            self.sample_formatted_response
        )
        
        assert 'language_info' in multi_lang
        lang_info = multi_lang['language_info']
        
        assert lang_info['primary_language'] == 'en'
        assert 'en' in lang_info['supported_languages']
        assert lang_info['regional_adaptation'] == 'east_africa'


class TestFormattingMetrics:
    """Test formatting metrics extraction."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ResponseFormatter()
        
        self.sample_formatted_response = {
            'formatted_response': {
                'user_type': 'farmer',
                'region': 'east_africa',
                'risk_level': 'high',
                'urgency': 'urgent',
                'recommendations': ['rec1', 'rec2'],
                'technical_details': None,
                'policy_recommendations': None
            }
        }
    
    def test_get_formatting_metrics_success(self):
        """Test successful formatting metrics extraction."""
        metrics = self.formatter.get_formatting_metrics(self.sample_formatted_response)
        
        assert metrics['user_type'] == 'farmer'
        assert metrics['region'] == 'east_africa'
        assert metrics['risk_level'] == 'high'
        assert metrics['urgency'] == 'urgent'
        assert metrics['recommendations_count'] == 2
        assert metrics['has_technical_details'] is False
        assert metrics['has_policy_recommendations'] is False
        assert metrics['formatting_success'] is True
    
    def test_get_formatting_metrics_with_error(self):
        """Test formatting metrics with error in response."""
        error_response = {
            'formatted_response': {
                'error': 'Formatting failed'
            }
        }
        
        metrics = self.formatter.get_formatting_metrics(error_response)
        
        assert metrics['formatting_success'] is False
    
    def test_get_formatting_metrics_exception_handling(self):
        """Test formatting metrics with invalid data."""
        invalid_response = None
        
        metrics = self.formatter.get_formatting_metrics(invalid_response)
        
        assert 'error' in metrics
        assert metrics['formatting_success'] is False


# Integration tests
class TestFormatterIntegration:
    """Integration tests for complete formatting workflows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ResponseFormatter()
    
    def test_complete_formatting_workflow_farmer(self):
        """Test complete formatting workflow for farmer."""
        # Start with merged response
        merged_response = {
            'terra_pulse_prediction': {
                'location': 'Turkana County, Kenya',
                'degradation_risk': 85,
                'risk_factors': ['bare_soil_increase', 'low_ndvi', 'high_variability'],
                'confidence': 0.9
            },
            'ai_insights': {
                'enhanced_recommendations': [
                    'Apply mulch immediately',
                    'Use drought-resistant crops',
                    'Implement water harvesting'
                ],
                'risk_assessment': 'Critical degradation risk',
                'success_probability': 0.65
            },
            'metadata': {
                'ai_enhancement_available': True,
                'processing_time': 150.0
            }
        }
        
        # Format for farmer
        formatted = self.formatter.format_response_for_user(merged_response, 'farmer')
        
        # Validate complete structure
        assert 'formatted_response' in formatted
        formatted_resp = formatted['formatted_response']
        
        # Check all required fields
        required_fields = [
            'user_type', 'region', 'risk_level', 'urgency', 
            'title', 'summary', 'recommendations'
        ]
        for field in required_fields:
            assert field in formatted_resp
        
        # Check farmer-specific fields
        assert 'farmer_message' in formatted_resp
        assert formatted_resp['technical_details'] is None
        assert formatted_resp['policy_recommendations'] is None
        
        # Extract metrics
        metrics = self.formatter.get_formatting_metrics(formatted)
        assert metrics['formatting_success'] is True
        assert metrics['user_type'] == 'farmer'
        
        # Create multi-language version
        multi_lang = self.formatter.create_multi_language_response(formatted)
        assert 'language_info' in multi_lang
    
    def test_complete_formatting_workflow_official(self):
        """Test complete formatting workflow for official."""
        merged_response = {
            'terra_pulse_prediction': {
                'location': 'Sahel Region, Mali',
                'degradation_risk': 65,
                'risk_factors': ['moderate_ndvi_drop'],
                'confidence': 0.8
            },
            'ai_insights': {
                'enhanced_recommendations': [
                    'Implement conservation programs',
                    'Provide technical assistance',
                    'Monitor degradation trends'
                ]
            },
            'metadata': {
                'ai_enhancement_available': True
            }
        }
        
        # Format for official
        formatted = self.formatter.format_response_for_user(merged_response, 'official')
        
        # Validate official-specific structure
        formatted_resp = formatted['formatted_response']
        
        assert formatted_resp['user_type'] == 'official'
        assert formatted_resp['region'] == 'west_africa'
        assert formatted_resp['technical_details'] is not None
        assert formatted_resp['policy_recommendations'] is not None
        assert 'official_summary' in formatted_resp
        
        # Validate policy recommendations content
        policy_recs = formatted_resp['policy_recommendations']
        assert len(policy_recs) > 0
        assert any('program' in rec.lower() for rec in policy_recs)


if __name__ == '__main__':
    pytest.main([__file__])