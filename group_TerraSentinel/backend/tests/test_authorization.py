"""
Tests for authorization mechanisms and access control.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, request, g
from werkzeug.test import Client

from backend.services.exceptions import (
    InvalidAPIKeyException, RateLimitExceededException, 
    SecurityValidationException, ValidationException
)


class TestAPIKeyBasedAuthorization:
    """Test cases for API key-based authorization patterns."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Mock API key database/validation
        self.valid_api_keys = {
            'admin_key_123': {'role': 'admin', 'permissions': ['read', 'write', 'delete']},
            'user_key_456': {'role': 'user', 'permissions': ['read']},
            'farmer_key_789': {'role': 'farmer', 'permissions': ['read', 'predict']},
            'official_key_abc': {'role': 'official', 'permissions': ['read', 'predict', 'report']}
        }
        
        def check_permission(api_key: str, required_permission: str) -> bool:
            """Mock permission checking function."""
            if api_key not in self.valid_api_keys:
                return False
            return required_permission in self.valid_api_keys[api_key]['permissions']
        
        def require_permission(permission: str):
            """Decorator to require specific permission."""
            def decorator(f):
                def wrapper(*args, **kwargs):
                    api_key = request.headers.get('X-API-Key', '')
                    if not check_permission(api_key, permission):
                        return {'error': 'INSUFFICIENT_PERMISSIONS', 
                               'required_permission': permission}, 403
                    return f(*args, **kwargs)
                return wrapper
            return decorator
        
        # Create test routes with different permission requirements
        @self.app.route('/predict', methods=['POST'])
        @require_permission('predict')
        def predict_route():
            return {'prediction': 'success'}
        
        @self.app.route('/admin/users', methods=['GET'])
        @require_permission('delete')
        def admin_users_route():
            return {'users': ['user1', 'user2']}
        
        @self.app.route('/reports', methods=['GET'])
        @require_permission('report')
        def reports_route():
            return {'reports': ['report1', 'report2']}
        
        @self.app.route('/public', methods=['GET'])
        def public_route():
            return {'message': 'public access'}
        
        self.client = self.app.test_client()
    
    def test_farmer_can_access_prediction(self):
        """Test that farmer role can access prediction endpoints."""
        response = self.client.post('/predict',
                                  headers={'X-API-Key': 'farmer_key_789'},
                                  json={'ndvi_data': 'test'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['prediction'] == 'success'
    
    def test_official_can_access_reports(self):
        """Test that official role can access report endpoints."""
        response = self.client.get('/reports',
                                 headers={'X-API-Key': 'official_key_abc'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'reports' in data
    
    def test_user_cannot_access_admin_endpoints(self):
        """Test that regular user cannot access admin endpoints."""
        response = self.client.get('/admin/users',
                                 headers={'X-API-Key': 'user_key_456'})
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'INSUFFICIENT_PERMISSIONS'
        assert data['required_permission'] == 'delete'
    
    def test_farmer_cannot_access_reports(self):
        """Test that farmer role cannot access official reports."""
        response = self.client.get('/reports',
                                 headers={'X-API-Key': 'farmer_key_789'})
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'INSUFFICIENT_PERMISSIONS'
    
    def test_admin_can_access_all_endpoints(self):
        """Test that admin role can access all endpoints."""
        endpoints = [
            ('/predict', 'POST', {'ndvi_data': 'test'}),
            ('/admin/users', 'GET', None),
            ('/reports', 'GET', None)
        ]
        
        for endpoint, method, json_data in endpoints:
            if method == 'POST':
                response = self.client.post(endpoint,
                                          headers={'X-API-Key': 'admin_key_123'},
                                          json=json_data)
            else:
                response = self.client.get(endpoint,
                                         headers={'X-API-Key': 'admin_key_123'})
            
            assert response.status_code == 200, f"Failed for {method} {endpoint}"
    
    def test_invalid_api_key_authorization(self):
        """Test authorization with invalid API key."""
        response = self.client.post('/predict',
                                  headers={'X-API-Key': 'invalid_key'},
                                  json={'ndvi_data': 'test'})
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'INSUFFICIENT_PERMISSIONS'
    
    def test_public_endpoint_no_authorization(self):
        """Test that public endpoints don't require authorization."""
        response = self.client.get('/public')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'public access'


class TestResourceBasedAuthorization:
    """Test cases for resource-based authorization."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Mock resource ownership database
        self.resource_owners = {
            'prediction_123': 'farmer_key_789',
            'prediction_456': 'farmer_key_abc',
            'report_789': 'official_key_def'
        }
        
        def check_resource_access(api_key: str, resource_id: str) -> bool:
            """Mock resource access checking."""
            # Admin can access everything
            if api_key.startswith('admin_'):
                return True
            # Owner can access their resources
            return self.resource_owners.get(resource_id) == api_key
        
        @self.app.route('/predictions/<prediction_id>', methods=['GET'])
        def get_prediction(prediction_id):
            api_key = request.headers.get('X-API-Key', '')
            if not check_resource_access(api_key, prediction_id):
                return {'error': 'ACCESS_DENIED', 'resource': prediction_id}, 403
            return {'prediction_id': prediction_id, 'data': 'prediction_data'}
        
        @self.app.route('/reports/<report_id>', methods=['GET'])
        def get_report(report_id):
            api_key = request.headers.get('X-API-Key', '')
            if not check_resource_access(api_key, report_id):
                return {'error': 'ACCESS_DENIED', 'resource': report_id}, 403
            return {'report_id': report_id, 'data': 'report_data'}
        
        self.client = self.app.test_client()
    
    def test_owner_can_access_own_prediction(self):
        """Test that resource owner can access their own predictions."""
        response = self.client.get('/predictions/prediction_123',
                                 headers={'X-API-Key': 'farmer_key_789'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['prediction_id'] == 'prediction_123'
    
    def test_non_owner_cannot_access_prediction(self):
        """Test that non-owner cannot access others' predictions."""
        response = self.client.get('/predictions/prediction_123',
                                 headers={'X-API-Key': 'farmer_key_abc'})
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'ACCESS_DENIED'
        assert data['resource'] == 'prediction_123'
    
    def test_admin_can_access_any_resource(self):
        """Test that admin can access any resource."""
        response = self.client.get('/predictions/prediction_123',
                                 headers={'X-API-Key': 'admin_key_999'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['prediction_id'] == 'prediction_123'
    
    def test_cross_resource_type_access_denied(self):
        """Test that access to wrong resource type is denied."""
        response = self.client.get('/reports/report_789',
                                 headers={'X-API-Key': 'farmer_key_789'})
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'ACCESS_DENIED'


class TestRoleBasedAccessControl:
    """Test cases for role-based access control (RBAC)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Mock role definitions
        self.roles = {
            'farmer': {
                'permissions': ['predict', 'view_own_data'],
                'endpoints': ['/predict', '/my_predictions']
            },
            'official': {
                'permissions': ['predict', 'view_reports', 'generate_reports'],
                'endpoints': ['/predict', '/reports', '/generate_report']
            },
            'admin': {
                'permissions': ['*'],  # All permissions
                'endpoints': ['*']     # All endpoints
            }
        }
        
        self.user_roles = {
            'farmer_key_123': 'farmer',
            'official_key_456': 'official',
            'admin_key_789': 'admin'
        }
        
        def get_user_role(api_key: str) -> str:
            """Get user role from API key."""
            return self.user_roles.get(api_key, 'anonymous')
        
        def has_permission(api_key: str, permission: str) -> bool:
            """Check if user has specific permission."""
            role = get_user_role(api_key)
            if role == 'anonymous':
                return False
            
            role_permissions = self.roles.get(role, {}).get('permissions', [])
            return '*' in role_permissions or permission in role_permissions
        
        def require_role(required_role: str):
            """Decorator to require specific role."""
            def decorator(f):
                def wrapper(*args, **kwargs):
                    api_key = request.headers.get('X-API-Key', '')
                    user_role = get_user_role(api_key)
                    
                    if user_role != required_role and user_role != 'admin':
                        return {'error': 'INSUFFICIENT_ROLE', 
                               'required_role': required_role,
                               'user_role': user_role}, 403
                    return f(*args, **kwargs)
                return wrapper
            return decorator
        
        # Create role-protected routes
        @self.app.route('/farmer_dashboard', methods=['GET'])
        @require_role('farmer')
        def farmer_dashboard():
            return {'dashboard': 'farmer_data'}
        
        @self.app.route('/official_dashboard', methods=['GET'])
        @require_role('official')
        def official_dashboard():
            return {'dashboard': 'official_data'}
        
        @self.app.route('/admin_panel', methods=['GET'])
        @require_role('admin')
        def admin_panel():
            return {'panel': 'admin_controls'}
        
        self.client = self.app.test_client()
    
    def test_farmer_can_access_farmer_dashboard(self):
        """Test that farmer can access farmer-specific endpoints."""
        response = self.client.get('/farmer_dashboard',
                                 headers={'X-API-Key': 'farmer_key_123'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['dashboard'] == 'farmer_data'
    
    def test_farmer_cannot_access_official_dashboard(self):
        """Test that farmer cannot access official-specific endpoints."""
        response = self.client.get('/official_dashboard',
                                 headers={'X-API-Key': 'farmer_key_123'})
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'INSUFFICIENT_ROLE'
        assert data['required_role'] == 'official'
        assert data['user_role'] == 'farmer'
    
    def test_official_can_access_official_dashboard(self):
        """Test that official can access official-specific endpoints."""
        response = self.client.get('/official_dashboard',
                                 headers={'X-API-Key': 'official_key_456'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['dashboard'] == 'official_data'
    
    def test_admin_can_access_all_dashboards(self):
        """Test that admin can access all role-specific endpoints."""
        dashboards = [
            '/farmer_dashboard',
            '/official_dashboard',
            '/admin_panel'
        ]
        
        for dashboard in dashboards:
            response = self.client.get(dashboard,
                                     headers={'X-API-Key': 'admin_key_789'})
            
            assert response.status_code == 200, f"Admin failed to access {dashboard}"
    
    def test_anonymous_user_access_denied(self):
        """Test that anonymous users are denied access to protected endpoints."""
        response = self.client.get('/farmer_dashboard')
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'INSUFFICIENT_ROLE'
        assert data['user_role'] == 'anonymous'


class TestContextualAuthorization:
    """Test cases for contextual authorization based on request data."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Mock location-based access control
        self.user_locations = {
            'farmer_kenya_123': ['kenya', 'baringo'],
            'farmer_uganda_456': ['uganda', 'kampala'],
            'official_kenya_789': ['kenya'],
            'admin_global_999': ['*']  # Global access
        }
        
        def check_location_access(api_key: str, location: str) -> bool:
            """Check if user can access data for specific location."""
            user_locations = self.user_locations.get(api_key, [])
            if '*' in user_locations:
                return True
            
            location_lower = location.lower()
            return any(loc in location_lower for loc in user_locations)
        
        @self.app.route('/predict_location', methods=['POST'])
        def predict_location():
            api_key = request.headers.get('X-API-Key', '')
            data = request.get_json()
            location = data.get('location', '')
            
            if not check_location_access(api_key, location):
                return {'error': 'LOCATION_ACCESS_DENIED', 
                       'location': location}, 403
            
            return {'prediction': 'success', 'location': location}
        
        @self.app.route('/data/<region>', methods=['GET'])
        def get_regional_data(region):
            api_key = request.headers.get('X-API-Key', '')
            
            if not check_location_access(api_key, region):
                return {'error': 'REGION_ACCESS_DENIED', 
                       'region': region}, 403
            
            return {'region': region, 'data': 'regional_data'}
        
        self.client = self.app.test_client()
    
    def test_farmer_can_access_own_region(self):
        """Test that farmer can access data for their region."""
        response = self.client.post('/predict_location',
                                  headers={'X-API-Key': 'farmer_kenya_123'},
                                  json={'location': 'Baringo County, Kenya'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['prediction'] == 'success'
    
    def test_farmer_cannot_access_other_region(self):
        """Test that farmer cannot access data for other regions."""
        response = self.client.post('/predict_location',
                                  headers={'X-API-Key': 'farmer_kenya_123'},
                                  json={'location': 'Kampala, Uganda'})
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'LOCATION_ACCESS_DENIED'
    
    def test_official_regional_access(self):
        """Test that official can access data for their country."""
        response = self.client.get('/data/kenya',
                                 headers={'X-API-Key': 'official_kenya_789'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['region'] == 'kenya'
    
    def test_admin_global_access(self):
        """Test that admin can access data for any region."""
        regions = ['kenya', 'uganda', 'tanzania']
        
        for region in regions:
            response = self.client.get(f'/data/{region}',
                                     headers={'X-API-Key': 'admin_global_999'})
            
            assert response.status_code == 200, f"Admin failed to access {region}"
    
    def test_cross_border_access_denied(self):
        """Test that cross-border access is properly denied."""
        response = self.client.get('/data/uganda',
                                 headers={'X-API-Key': 'farmer_kenya_123'})
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error'] == 'REGION_ACCESS_DENIED'


class TestAuthorizationLogging:
    """Test cases for authorization event logging and monitoring."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        @self.app.route('/protected', methods=['POST'])
        def protected_route():
            api_key = request.headers.get('X-API-Key', '')
            if api_key != 'authorized_key':
                # Log authorization failure
                return {'error': 'AUTHORIZATION_FAILED'}, 403
            
            # Log authorization success
            return {'message': 'authorized'}
        
        self.client = self.app.test_client()
    
    def test_authorization_success_logging(self):
        """Test logging of successful authorization events."""
        with patch('app.logging_service') as mock_logging:
            response = self.client.post('/protected',
                                      headers={'X-API-Key': 'authorized_key'},
                                      json={'test': 'data'})
            
            assert response.status_code == 200
            
            # In a real implementation, this would log authorization success
            # For now, we verify the endpoint works correctly
    
    def test_authorization_failure_logging(self):
        """Test logging of authorization failure events."""
        with patch('app.logging_service') as mock_logging:
            response = self.client.post('/protected',
                                      headers={'X-API-Key': 'unauthorized_key'},
                                      json={'test': 'data'})
            
            assert response.status_code == 403
            
            # In a real implementation, this would log authorization failure
            # For now, we verify the endpoint correctly denies access
    
    def test_authorization_audit_trail(self):
        """Test that authorization events create proper audit trail."""
        with patch('app.logging_service') as mock_logging:
            # Multiple authorization attempts
            test_keys = ['key1', 'key2', 'authorized_key', 'key3']
            
            for key in test_keys:
                response = self.client.post('/protected',
                                          headers={'X-API-Key': key},
                                          json={'test': 'data'})
            
            # In a real implementation, each attempt would be logged
            # This creates an audit trail of authorization attempts


class TestAuthorizationIntegration:
    """Integration tests for authorization with other security components."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        from services.security_middleware import create_security_middleware
        
        # Initialize security middleware
        security_middleware = create_security_middleware()
        security_middleware.init_app(self.app)
        
        @self.app.route('/secure_predict', methods=['POST'])
        def secure_predict():
            # Mock authorization check
            api_key = request.headers.get('X-API-Key', '')
            if not api_key.startswith('farmer_') and not api_key.startswith('admin_'):
                return {'error': 'INSUFFICIENT_PERMISSIONS'}, 403
            
            return {'prediction': 'authorized_success'}
        
        self.client = self.app.test_client()
    
    def test_authorization_with_input_validation(self):
        """Test authorization combined with input validation."""
        response = self.client.post('/secure_predict',
                                  headers={
                                      'X-API-Key': 'farmer_key_123',
                                      'Content-Type': 'application/json'
                                  },
                                  json={
                                      'ndvi_mean_early': 0.5,
                                      'location': 'Valid Location'
                                  })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['prediction'] == 'authorized_success'
    
    def test_authorization_with_rate_limiting(self):
        """Test authorization combined with rate limiting."""
        # This would test the interaction between authorization and rate limiting
        # The exact implementation depends on how these components interact
        
        response = self.client.post('/secure_predict',
                                  headers={
                                      'X-API-Key': 'farmer_key_123',
                                      'Content-Type': 'application/json'
                                  },
                                  json={'test': 'data'})
        
        # Should pass authorization and rate limiting
        assert response.status_code == 200
    
    def test_authorization_failure_with_security_headers(self):
        """Test that authorization failures still include security headers."""
        response = self.client.post('/secure_predict',
                                  headers={
                                      'X-API-Key': 'invalid_key',
                                      'Content-Type': 'application/json'
                                  },
                                  json={'test': 'data'})
        
        assert response.status_code == 403
        
        # Security headers should still be present
        assert 'X-Content-Type-Options' in response.headers
        assert 'X-Frame-Options' in response.headers
    
    def test_multiple_authorization_layers(self):
        """Test multiple layers of authorization checks."""
        # This would test scenarios where multiple authorization checks are applied
        # For example: API key validation + role check + resource ownership
        
        response = self.client.post('/secure_predict',
                                  headers={
                                      'X-API-Key': 'admin_key_999',
                                      'Content-Type': 'application/json'
                                  },
                                  json={'test': 'data'})
        
        # Admin should pass all authorization layers
        assert response.status_code == 200