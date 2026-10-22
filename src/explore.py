import json


with open('data/CUADv1.json', 'r', encoding='utf-8') as file:
    data = json.load(file)
    print(data.keys())
    print(type(data['data']))
    print(len(data['data']))
    first = data['data'][0]
    print(first.keys())
    print(first['title'])
    print(type(first['paragraphs']))
    print(len(first['paragraphs']))
    para = first['paragraphs'][0]
    print(para.keys())
    print(type(para['qas']))
    print(len(para['qas']))
    print(len(para['context']))
    qa = para['qas'][0]
    print(qa.keys())
    
first = data['data'][0]
qas = first['paragraphs'][0]['qas']

for qa in qas:
    if qa['id'].endswith('Governing Law'):
        print(qa['id'])
        print(qa['is_impossible'])
        
        
has_clause = 0
no_clause = 0

for contract in data['data']:
    qas = contract['paragraphs'][0]['qas']
    for qa in qas:
        if qa['id'].endswith('Governing Law'):
            if qa['is_impossible'] == False:
                has_clause += 1
            else:
                no_clause += 1

print(has_clause)
print(no_clause)
print(has_clause + no_clause)


contract = data['data'][0]
paragraph = contract['paragraphs'][0]
context = paragraph['context']

for qa in paragraph['qas']:
    if qa['id'].endswith('Governing Law'):
        for answer in qa['answers']:
            start = answer['answer_start']
            text = answer['text']
            piece = context[start: start + len(text)]
            print(piece == text)


matches = 0
mismatches = 0

for contract in data['data']:
    paragraph = contract['paragraphs'][0]
    context = paragraph['context']
    for qa in paragraph['qas']:
        if qa['id'].endswith('Governing Law'):
            for answer in qa['answers']:
                start = answer['answer_start']
                text = answer['text']
                if context[start:start + len(text)] == text:
                    matches += 1
                else:
                    mismatches += 1

print(matches)
print(mismatches)