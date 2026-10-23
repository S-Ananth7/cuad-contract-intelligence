
import json
import random

with open('data/CUADv1.json', 'r', encoding = 'utf-8') as file:
    data = json.load(file)

present = []
absent = []

for contract in data['data']:
    for qa in contract['paragraphs'][0]['qas']:
        if qa['id'].endswith('Governing Law'):
            if qa['is_impossible'] == False:
                present.append(contract['title'])
            else:
                absent.append(contract['title'])
present.sort()
absent.sort()

rng = random.Random(43)
rng.shuffle(present)
rng.shuffle(absent)

splits ={
    'dev': present[:22] + absent[:8],
    'test': present[22:44] + absent[8:16]
}

print(len(present), len(absent))
print(len(splits['dev']), len(splits['test']))
print(set(splits['dev']) & set(splits['test']))

with open('data/splits.json', 'w', encoding='utf-8') as file:
    json.dump(splits, file, indent=2)

dev_companies = {t.split('_')[0] for t in splits['dev']}
test_companies = {t.split('_')[0] for t in splits['test']}
#print(dev_companies, test_companies)
print(dev_companies & test_companies)