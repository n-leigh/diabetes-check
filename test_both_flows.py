"""
test_both_flows.py
Verifies Flow A (with lab values) and Flow B (without lab values).
"""

import urllib.request
import urllib.parse
import http.cookiejar
import re

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# Flow A: with labs
h = opener.open('http://127.0.0.1:5000/assessment').read().decode('utf-8')
csrf = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', h).group(1)
payload_a = {
    'csrf_token': csrf, 'Age': '9', 'Sex': '1', 'BMI': '28.5',
    'HighBP': '1', 'HighChol': '1', 'Smoker': '0', 'HeartDiseaseorAttack': '0',
    'Stroke': '0', 'DiffWalk': '0', 'PhysHlth': '2', 'GenHlth': '2',
    'MentHlth': '1', 'NoDocbcCost': '0',
    'DiabetesDuration': '2', 'BlurryVision': '1',
    'LabHbA1c': '7.2', 'LabSystolicBP': '132', 'LabLDL': '110'
}
r_a = opener.open(urllib.request.Request('http://127.0.0.1:5000/predict', data=urllib.parse.urlencode(payload_a).encode('utf-8'))).read().decode('utf-8')
assert 'Lab-Based Clinical Assessment' in r_a
print('Flow A (with labs provided): PASSED')

# Flow B: without labs (skipped)
h2 = opener.open('http://127.0.0.1:5000/assessment').read().decode('utf-8')
csrf2 = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', h2).group(1)
payload_b = {
    'csrf_token': csrf2, 'Age': '8', 'Sex': '0', 'BMI': '26.0',
    'HighBP': '0', 'HighChol': '0', 'Smoker': '0', 'HeartDiseaseorAttack': '0',
    'Stroke': '0', 'DiffWalk': '0', 'PhysHlth': '0', 'GenHlth': '2',
    'MentHlth': '0', 'NoDocbcCost': '0',
    'DiabetesDuration': '1', 'BlurryVision': '0'
}
r_b = opener.open(urllib.request.Request('http://127.0.0.1:5000/predict', data=urllib.parse.urlencode(payload_b).encode('utf-8'))).read().decode('utf-8')
assert 'Tip for your next doctor' in r_b
assert 'Cardiovascular (ACC/AHA)' in r_b
print('Flow B (without labs, graceful degradation): PASSED')

print('\n[SUCCESS: BOTH TIERED FLOWS VERIFIED 100%]')
