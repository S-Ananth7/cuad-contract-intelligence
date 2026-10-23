import json

with open('data/CUADv1.json', 'r', encoding='utf-8') as file:
    data = json.load(file)
    
with  open('data/splits.json', 'r', encoding='utf-8') as file:
    splits = json.load(file)

title = splits['dev'][0]

for contract in data['data']:
    if contract['title'] == title:
        text = contract['paragraphs'][0]['context']
        with open('data/one_contract.txt', 'w', encoding='utf-8') as out:
            out.write(text)
        print(title, len(text))