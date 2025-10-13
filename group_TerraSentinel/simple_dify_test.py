#!/usr/bin/env python3

print("Testing simple DifyService creation...")

try:
    from services.base_service import BaseService
    from config.settings import get_config
    import requests
    from datetime import datetime
    
    print("Creating simple DifyService...")
    
    class SimpleDifyService(BaseService):
        def __init__(self):
            super().__init__("dify")
            print("BaseService initialized")
            
            self.config = get_config()
            print("Config loaded")
            
        def _validate_configuration(self) -> bool:
            print("Validating configuration...")
            return True
        
        async def _perform_health_check(self):
            print("Performing health check...")
            return {"status": "ok"}
    
    print("Creating service instance...")
    service = SimpleDifyService()
    print(f"Service created successfully: {service}")
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()