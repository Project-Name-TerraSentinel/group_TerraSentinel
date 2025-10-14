import sys, json, logging, os
# write detailed logs to a file
log_path = os.path.join(os.path.dirname(__file__), 'smoke_verbose.log')
logging.basicConfig(level=logging.DEBUG, filename=log_path, filemode='w',
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')

sys.path.insert(0, '.')
from backend import app as application
client = application.app.test_client()

out = {}
try:
    r = client.post('/predict', json={'latitude':0.52,'longitude':36.08}, headers={'X-API-Key':'local-dev-key'})
    out['predict'] = {'status': r.status_code, 'body': r.get_json()}
except Exception as e:
    out['predict'] = {'error': str(e)}

try:
    r2 = client.post('/ai', json={'prompt':'Give one short action','metadata':{'lat':0.52,'lon':36.08,'score':70}}, headers={'X-API-Key':'local-dev-key'})
    out['ai'] = {'status': r2.status_code, 'body': r2.get_json()}
except Exception as e:
    out['ai'] = {'error': str(e)}

with open(os.path.join(os.path.dirname(__file__), 'smoke_output_verbose.json'),'w') as f:
    json.dump(out, f, indent=2)

print('WROTE', os.path.join(os.path.dirname(__file__), 'smoke_output_verbose.json'))
print('LOG:', log_path)
