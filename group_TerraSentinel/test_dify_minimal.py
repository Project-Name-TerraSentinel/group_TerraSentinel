#!/usr/bin/env python3

print("Creating minimal DifyService in separate file...")

from backend.services.base_service import BaseService
from backend.config.settings import get_config

class DifyService(BaseService):
    def __init__(self):
        super().__init__("dify")
        self.config = get_config()
    
    def _validate_configuration(self) -> bool:
        return True
    
    async def _perform_health_check(self):
        return {"status": "ok"}

print("Testing DifyService creation...")
service = DifyService()
print(f"Service created: {service}")
print("Success!")