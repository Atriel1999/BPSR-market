import json

with open(r'data/items.json', encoding='utf-8') as f:
    data = json.load(f)

cat_order = ['식물학','광물학','결정학','요리','연금술','주조','공예','목공','직조']

def sort_key(item):
    key, val = item
    cat = val.get('category', '미분류')
    season = val.get('season', 1)
    cat_idx = cat_order.index(cat) if cat in cat_order else 99
    if key.isdigit():
        num = int(key)
    elif key.startswith('season2_'):
        suffix = key.replace('season2_', '').rstrip('b')
        num = 9000000 + int(suffix) if suffix.isdigit() else 9999999
    else:
        num = 9999999
    return (cat_idx, -season, num)

sorted_result = dict(sorted(data.items(), key=sort_key))

with open(r'data/items.json', 'w', encoding='utf-8') as f:
    json.dump(sorted_result, f, ensure_ascii=False, indent=2)

print("정렬 완료")