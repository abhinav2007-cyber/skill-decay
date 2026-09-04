import urllib.request, json

req = urllib.request.urlopen('http://localhost:8000/skills')
data = json.loads(req.read())
print('Status:', req.status)
print('User:', data['user_id'])
print('Simulated now:', data['simulated_now'])
skills = list(data['skills'].keys())
print('Skills:', skills)
first_skill = skills[0]
first_st = list(data['skills'][first_skill].keys())[0]
b = data['skills'][first_skill][first_st]
kt = b['knowledge_tracking']
decay = b['decay']
print(f'First sub-topic: {first_skill}/{first_st}')
print('  mode:', kt['mode'])
print('  decay_score:', decay['decay_score'])
print('  obs_count:', kt['observation_count'])
