import json, collections
path = 'data/raw/hadith/meeatif/bukhari_enriched_v2.json'
data = json.load(open(path, encoding='utf-8'))

duplicates = collections.Counter()
prophetic_types = collections.Counter()

for r in data:
    if r.get('is_stub'): continue
    
    # Check duplicates
    global_num = r.get('hadith_global_num')
    if global_num is None:
        hadith_id = r.get('hadith_id')
        import re
        match = re.search(r'(?:bukhari:)(\d+)', str(hadith_id).strip())
        global_num = int(match.group(1)) if match else None
        
    if global_num:
        duplicates[global_num] += 1
        
    prop = r.get('has_direct_prophetic_statement')
    prophetic_types[(type(prop), prop)] += 1

dups = {k: v for k, v in duplicates.items() if v > 1}
print(f'Duplicate hadith numbers: {sum(v-1 for k, v in dups.items())} over {len(dups)} numbers')

print('Prophetic statement values:')
for k, v in prophetic_types.items():
    print(f'{k}: {v}')
