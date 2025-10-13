#!/usr/bin/env python3

print("Testing config loading...")

try:
    from config.settings import get_config
    
    print("Getting config...")
    config = get_config()
    
    print(f"Config type: {type(config)}")
    print(f"Dify API key: {config.dify_api_key}")
    print(f"Dify workflow ID: {config.dify_workflow_id}")
    print(f"Dify API endpoint: {config.dify_api_endpoint}")
    print(f"Model path: {config.terra_pulse_model_path}")
    
    print("Config loaded successfully!")
    
except Exception as e:
    import traceback
    print(f"Config error: {e}")
    traceback.print_exc()