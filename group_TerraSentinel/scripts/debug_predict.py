import sys, traceback
sys.path.insert(0, '.')
from backend import app as application
from flask import Request

with application.app.test_request_context('/predict', method='POST', json={'latitude':0.52,'longitude':36.08} , headers={'X-API-Key':'local-dev-key'}):
    try:
        # Call the view function directly
        rv = application.app.view_functions['predict']()
        print('Return:', rv)
    except Exception as e:
        traceback.print_exc()
