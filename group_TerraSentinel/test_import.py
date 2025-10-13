#!/usr/bin/env python3

try:
    print("Importing BaseService...")
    from services.base_service import BaseService
    print("BaseService imported successfully")
    
    print("Importing get_config...")
    from config.settings import get_config
    print("get_config imported successfully")
    
    print("Importing other dependencies...")
    import requests
    import aiohttp
    from pydantic import BaseModel
    print("Dependencies imported successfully")
    
    print("Importing dify_service module...")
    import services.dify_service as dify_module
    print("dify_service module imported successfully")
    
    print("Module contents:", dir(dify_module))
    
    print("Importing DifyService class...")
    from services.dify_service import DifyService
    print("DifyService imported successfully")
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    print("Traceback:")
    traceback.print_exc()