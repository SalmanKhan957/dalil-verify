import json, pathlib

p = pathlib.Path('data/raw/hadith/meeatif/Sahih al-Bukhari.json')
data = json.loads(p.read_text(encoding='utf-8'))
records = data if isinstance(data, list) else []
print(f'old records: {len(records)}')
if records:
    print('old keys:', sorted(records[0].keys()))
    has_arabic = sum(1 for r in records if r.get('Arabic_Text'))
    has_ref = sum(1 for r in records if r.get('Reference'))
    print(f'Arabic_Text present: {has_arabic}')
    print(f'Reference present: {has_ref}')
    # Show sample
    print('sample Reference:', records[0].get('Reference'))
