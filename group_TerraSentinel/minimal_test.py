#!/usr/bin/env python3

print("Testing minimal DifyService...")

try:
    print("Step 1: Testing config import...")
    from config.settings import get_config
    config = get_config()
    print(f"Config loaded: {type(config)}")
    
    print("Step 2: Testing BaseService import...")
    from services.base_service import BaseService
    print(f"BaseService loaded: {BaseService}")
    
    print("Step 3: Creating minimal class...")
    
    class TestService(BaseService):
        def __init__(self):
            super().__init__("test")
        
        def _validate_configuration(self) -> bool:
            return True
        
        async def _perform_health_check(self):
            return {"status": "ok"}
    
    print("Step 4: Testing class instantiation...")
    service = TestService()
    print(f"Service created: {service}")
    
    print("All tests passed!")
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()