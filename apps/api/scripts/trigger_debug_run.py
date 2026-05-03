import time
import json
import urllib.request

url = 'http://localhost:8000/api/battlecard/generate'
data = {'competitor_name': 'Pipeline Debug Test', 'mode': 'live'}
req = urllib.request.Request(url, data=bytes(json.dumps(data), encoding='utf-8'), headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
out = json.load(resp)
print('POST response:', out)
run_id = out.get('run_id')
if not run_id:
    raise SystemExit('no run_id')
print('Polling run', run_id)
for i in range(120):
    time.sleep(2)
    try:
        rb = json.load(urllib.request.urlopen(f'http://localhost:8000/api/battlecard/{run_id}'))
    except Exception as e:
        print('poll error', e)
        continue
    status = rb.get('status')
    print(i, 'status=', status)
    if status in ('completed','failed'):
        print('Final status:', status)
        print('Run summary confidence:', (rb.get('battlecard') or {}).get('summary',{}).get('confidence_score'))
        break
else:
    print('Timed out waiting for run to complete')
print('Done')
