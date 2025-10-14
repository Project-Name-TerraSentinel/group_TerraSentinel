import sys, json, logging
# reduce logging so test output is readable
logging.getLogger().setLevel(logging.CRITICAL)

sys.path.insert(0, '.')
from backend import app as application
client = application.app.test_client()

print('SMOKE TEST START')
# Test /predict with lat/lon
r = client.post('/predict', json={'latitude':0.52,'longitude':36.08}, headers={'X-API-Key':'local-dev-key'})
out = {
  'predict': {
    'status': r.status_code,
    'body': r.get_json()
  }
}

# Test /ai with prompt
r2 = client.post('/ai', json={'prompt':'Give one short action','metadata':{'lat':0.52,'lon':36.08,'score':70}}, headers={'X-API-Key':'local-dev-key'})
out['ai'] = {'status': r2.status_code, 'body': r2.get_json()}

import os
out_path = os.path.join(os.path.dirname(__file__), 'smoke_output.json')
with open(out_path,'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2)

print('WROTE', out_path)
