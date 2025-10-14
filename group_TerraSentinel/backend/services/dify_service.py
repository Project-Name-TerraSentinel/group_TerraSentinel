"""Dify API integration service."""

import json
import asyncio
import aiohttp
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, validator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.services.base_service import BaseService, ServiceHealthCheck, ServiceStatus
from backend.config.settings import get_config


class DifyWorkflowInput(BaseModel):
    """Data model for Dify workflow input."""
    degradation_risk: int = Field(..., ge=0, le=100, description="Degradation risk percentage")
    risk_factors: List[str] = Field(..., min_items=1, description="List of risk factors")
    location: str = Field(..., min_length=1, description="Location information")
    user_context: str = Field(..., min_length=1, description="User context information")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence")
    recommended_action_key: str = Field(..., min_length=1, description="Recommended action key")
    user_type: str = Field(default="farmer", description="User type")
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('user_type')
    def validate_user_type(cls, v):
        if v not in ['farmer', 'official']:
            raise ValueError('user_type must be either "farmer" or "official"')
        return v


class DifyAPIRequest(BaseModel):
    """Data model for Dify API request."""
    inputs: Dict[str, Any] = Field(..., description="Input data for the workflow")
    response_mode: str = Field(default="blocking", description="Response mode")
    user: str = Field(default="api-user", description="User identifier")
    
    @validator('response_mode')
    def validate_response_mode(cls, v):
        if v not in ['blocking', 'streaming']:
            raise ValueError('response_mode must be either "blocking" or "streaming"')
        return v


class DifyAPIResponse(BaseModel):
    """Data model for Dify API response."""
    workflow_run_id: str
    task_id: Optional[str] = None
    status: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    elapsed_time: float
    total_tokens: Optional[int] = None
    created_at: int


class DifyWorkflowResponse(BaseModel):
    """Data model for processed Dify workflow response."""
    workflow_run_id: str
    status: str
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    elapsed_time: float


class DifyService(BaseService):
    """Service for integrating with Dify API workflows."""
    
    def __init__(self):
        # Set config before calling super() since _validate_configuration needs it
        self.config = get_config()
        super().__init__("dify")
        self._setup_http_session()
        self.base_url = self.config.dify_api_endpoint
    
    def _validate_configuration(self) -> bool:
        """Validate Dify service configuration."""
        if not self.config.dify_api_key:
            raise ValueError("Dify API key is required")
        if not self.config.dify_workflow_id:
            raise ValueError("Dify workflow ID is required")
        if not self.config.dify_api_endpoint:
            raise ValueError("Dify API endpoint is required")
        return True
    
    def _setup_http_session(self):
        """Set up HTTP session with authentication and retry logic."""
        self.session = requests.Session()
        
        # Set authentication headers
        self.session.headers.update({
            'Authorization': f'Bearer {self.config.dify_api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'Terra-Pulse-Integration/1.0'
        })
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _perform_health_check(self) -> ServiceHealthCheck:
        """Perform health check against Dify API."""
        try:
            url = f"{self.base_url}/health"
            response = self.session.get(url, timeout=self.config.timeout_seconds)
            response.raise_for_status()
            
            return ServiceHealthCheck(
                status=ServiceStatus.HEALTHY,
                message="Dify API is accessible",
                response_time_ms=response.elapsed.total_seconds() * 1000
            )
        except Exception as e:
            return ServiceHealthCheck(
                status=ServiceStatus.UNHEALTHY,
                message=f"Dify API health check failed: {str(e)}",
                error=str(e)
            )
    
    def health_check(self) -> Dict[str, Any]:
        """Check Dify API health and connectivity."""
        try:
            url = f"{self.base_url}/health"
            response = self.session.get(url, timeout=self.config.timeout_seconds)
            response.raise_for_status()
            
            return {
                'service': 'dify',
                'status': 'healthy',
                'response_time': response.elapsed.total_seconds(),
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'service': 'dify',
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def format_terra_pulse_for_dify(self, terra_pulse_result: Dict[str, Any]) -> DifyWorkflowInput:
        """Format Terra Pulse prediction result for Dify workflow input."""
        required_fields = ['degradation_risk', 'risk_factors', 'location', 
                          'user_context', 'confidence', 'recommended_action_key']
        
        for field in required_fields:
            if field not in terra_pulse_result:
                raise ValueError(f"Missing required field: {field}")
        
        return DifyWorkflowInput(
            degradation_risk=terra_pulse_result['degradation_risk'],
            risk_factors=terra_pulse_result['risk_factors'],
            location=terra_pulse_result['location'],
            user_context=terra_pulse_result['user_context'],
            confidence=terra_pulse_result['confidence'],
            recommended_action_key=terra_pulse_result['recommended_action_key'],
            user_type=terra_pulse_result.get('user_type', 'farmer'),
            additional_context=terra_pulse_result.get('additional_context', {})
        )
    
    def trigger_workflow_sync(self, workflow_input: DifyWorkflowInput) -> DifyWorkflowResponse:
        """Trigger Dify workflow synchronously."""
        try:
            url = f"{self.base_url}/workflows/{self.config.dify_workflow_id}/run"
            
            # Prepare request data
            request_data = DifyAPIRequest(
                inputs=workflow_input.dict(),
                response_mode="blocking",
                user=f"terra-pulse-{workflow_input.user_type}"
            )
            
            # Make API call
            response = self.session.post(
                url,
                data=json.dumps(request_data.dict()),
                timeout=self.config.timeout_seconds
            )
            response.raise_for_status()
            
            # Parse response
            api_response = DifyAPIResponse(**response.json())
            
            # Process and return workflow response
            return DifyWorkflowResponse(
                workflow_run_id=api_response.workflow_run_id,
                status="completed" if api_response.status == "succeeded" else "failed",
                outputs=api_response.data or {},
                error=api_response.error.get('message') if api_response.error else None,
                elapsed_time=api_response.elapsed_time
            )
            
        except Exception as e:
            return DifyWorkflowResponse(
                workflow_run_id="error",
                status="failed",
                outputs={},
                error=str(e),
                elapsed_time=0.0
            )
    
    def trigger_workflow_sync_wrapper(self, workflow_input: DifyWorkflowInput) -> DifyWorkflowResponse:
        """Wrapper for sync workflow execution (for testing)."""
        return self.trigger_workflow_sync(workflow_input)
    
    async def trigger_workflow_async(self, workflow_input: DifyWorkflowInput) -> DifyWorkflowResponse:
        """Trigger Dify workflow asynchronously."""
        try:
            url = f"{self.base_url}/workflows/{self.config.dify_workflow_id}/run"
            
            # Prepare request data
            request_data = DifyAPIRequest(
                inputs=workflow_input.dict(),
                response_mode="blocking",
                user=f"terra-pulse-{workflow_input.user_type}"
            )
            
            headers = {
                'Authorization': f'Bearer {self.config.dify_api_key}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=json.dumps(request_data.dict()),
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    response.raise_for_status()
                    response_data = await response.json()
                    
                    # Parse response
                    api_response = DifyAPIResponse(**response_data)
                    
                    return DifyWorkflowResponse(
                        workflow_run_id=api_response.workflow_run_id,
                        status="completed" if api_response.status == "succeeded" else "failed",
                        outputs=api_response.data or {},
                        error=api_response.error.get('message') if api_response.error else None,
                        elapsed_time=api_response.elapsed_time
                    )
                    
        except Exception as e:
            return DifyWorkflowResponse(
                workflow_run_id="async-error",
                status="failed",
                outputs={},
                error=str(e),
                elapsed_time=0.0
            )
    
    def process_workflow_response(self, workflow_response: DifyWorkflowResponse) -> Dict[str, Any]:
        """Process Dify workflow response into standardized format."""
        if workflow_response.status == "completed":
            outputs = workflow_response.outputs
            return {
                'status': 'success',
                'workflow_run_id': workflow_response.workflow_run_id,
                'enhanced_recommendations': outputs.get('recommendations', []),
                'risk_assessment': outputs.get('risk_assessment', ''),
                'timeline': outputs.get('timeline', ''),
                'cost_estimate': outputs.get('cost_estimate', ''),
                'success_probability': outputs.get('success_probability', 0.0),
                'additional_insights': outputs.get('additional_insights', {}),
                'processing_time': workflow_response.elapsed_time
            }
        else:
            return {
                'status': 'failed',
                'workflow_run_id': workflow_response.workflow_run_id,
                'error': workflow_response.error or 'Unknown error',
                'enhanced_recommendations': [],
                'risk_assessment': '',
                'timeline': '',
                'cost_estimate': '',
                'success_probability': 0.0,
                'additional_insights': {},
                'processing_time': workflow_response.elapsed_time
            }
    
    def _create_fallback_response(self, workflow_input: DifyWorkflowInput) -> Dict[str, Any]:
        """Create fallback response when Dify API is unavailable."""
        # Generate basic recommendations based on risk level and user type
        risk_level = workflow_input.degradation_risk
        user_type = workflow_input.user_type
        
        if risk_level >= 70:
            timeline = "Immediate action required within 7 days"
            if user_type == "farmer":
                recommendations = [
                    "Apply emergency soil protection measures immediately",
                    "Use available crop residue or mulch to cover bare soil",
                    "Implement practical water conservation techniques"
                ]
            else:
                recommendations = [
                    "Deploy emergency soil conservation policy programs",
                    "Coordinate with local farmers for immediate intervention",
                    "Activate drought response policy protocols"
                ]
        elif risk_level >= 40:
            timeline = "Action recommended within 2-4 weeks"
            if user_type == "farmer":
                recommendations = [
                    "Apply practical soil conservation measures for next season",
                    "Consider cover crops or improved varieties",
                    "Implement gradual land management improvements"
                ]
            else:
                recommendations = [
                    "Develop medium-term conservation policy programs",
                    "Provide technical assistance to affected farmers",
                    "Monitor degradation trends closely"
                ]
        else:
            timeline = "Regular monitoring and preventive measures"
            if user_type == "farmer":
                recommendations = [
                    "Continue current practical sustainable practices",
                    "Monitor soil health regularly",
                    "Apply good agricultural practices"
                ]
            else:
                recommendations = [
                    "Continue regular monitoring policy programs",
                    "Support preventive conservation initiatives",
                    "Maintain early warning systems"
                ]
        
        return {
            'status': 'fallback',
            'workflow_run_id': 'fallback-response',
            'enhanced_recommendations': recommendations,
            'risk_assessment': f"Automated assessment based on {risk_level}% degradation risk",
            'timeline': timeline,
            'cost_estimate': "Variable based on local conditions",
            'success_probability': max(0.3, 1.0 - (risk_level / 100)),
            'additional_insights': {
                'location': workflow_input.location,
                'user_type': user_type,
                'confidence': workflow_input.confidence,
                'fallback_reason': 'Dify API unavailable'
            },
            'processing_time': 0.1
        }
    
    def process_workflow_with_fallback(self, workflow_input: DifyWorkflowInput) -> Dict[str, Any]:
        """Process workflow with fallback to basic response if Dify fails."""
        try:
            # Try to execute workflow
            workflow_response = self.trigger_workflow_sync_wrapper(workflow_input)
            
            if workflow_response.status == "completed":
                return self.process_workflow_response(workflow_response)
            else:
                # Workflow failed, use fallback
                return self._create_fallback_response(workflow_input)
                
        except Exception:
            # Any exception, use fallback
            return self._create_fallback_response(workflow_input)
    
    def _should_retry(self, exception: Exception) -> bool:
        """Determine if request should be retried based on exception type."""
        retry_exceptions = (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError
        )
        return isinstance(exception, retry_exceptions)