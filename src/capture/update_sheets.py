"""
생활클래스 수익 계산 → Google Sheets 업데이트
"""

import json
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
ITEMS_FILE = BASE_DIR / 'data' / 'items.json'
CONFIG_FILE = BASE_DIR / 'data' / 'production_config.json'
CRED_FILE = list(Path(r'C:\dev_source\BPSRMarket\src\data\credentials').glob('*.json'))[0]
SHEET_ID = '1bfUinb_Ve10pncEAlaP6EPFhal0-W9_yith_tQjyLNE'

with open(ITEMS_FILE, encoding='utf-8') as f:
    items_db = json.load(f)
with open(CONFIG_FILE, encoding='utf-8') as f:
    config = json.load(f)

def get_price(config_id):
    cid = str(config_id)
    if cid in config['exceptions']:
        fp = config['exceptions'][cid].get('fallback_price')
        if fp:
            return fp
    item = items_db.get(cid)
    if item and item.get('price'):
        return item['price']
    return None

def get_name(config_id):
    cid = str(config_id)
    for k, v in items_db.items():
        if k == cid or v.get('kor_name') == cid:
            return v['kor_name']
    return cid

def get_item_time(config_id):
    cid = str(config_id)
    item = items_db.get(cid)
    if item and item.get('updated_at'):
        try:
            dt = datetime.fromisoformat(item['updated_at'])
            return dt.strftime('%m-%d %H:%M')
        except:
            return item['updated_at']
    return ''

def capture_time():
    times = [v['updated_at'] for v in items_db.values() if v.get('updated_at')]
    if times:
        latest = max(times)
        try:
            dt = datetime.fromisoformat(latest)
            return dt.strftime('%Y-%m-%d %H:%M')
        except:
            return latest
    return '캡처 정보 없음'

scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file(str(CRED_FILE), scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)
print('시트 열기 완료')
ws = sh.sheet1
ws.clear()

rows = []
cap_time = capture_time()
vitality_cell = 'B2'

category_header_rows = []
col_header_rows = []
item_name_rows = []
data_ranges = []

def add_blank():
    rows.append([''])

def add_header(title):
    category_header_rows.append(len(rows) + 1)
    rows.append([f'■ {title}', '', f'캡처: {cap_time}'])

def add_col_header(cols):
    col_header_rows.append((len(rows) + 1, len(cols) + 1))
    rows.append(cols + ['캡처시간'])

def add_item_row(row_data):
    item_name_rows.append(len(rows) + 1)
    rows.append(row_data)

rows.append(['생활력 입력 (이 값을 수정하세요)'])
rows.append(['생활력', 400])
add_blank()

# ======================================================
# 채집
# ======================================================
harvest_cats = {
    '식물학': config['harvest']['식물학'],
    '광물학(일반)': config['harvest']['광물학_일반'],
    '광물학(운철)': config['harvest']['광물학_운철'],
    '결정학': config['harvest']['결정학'],
    '목공': config['harvest']['목공'],
}

for cat_name, cat in harvest_cats.items():
    add_header(cat_name)
    vpa = cat['vitality_per_action']
    add_col_header(['아이템명', '마켓가격', f'생활력{vpa}당 생산량', '생활력400 수익', f'생활력{vitality_cell}기준 수익'])
    cat_start = len(rows) + 1
    items_list = cat['items']
    for item_entry in items_list:
        if isinstance(item_entry, dict):
            cid = item_entry['id']
            ye = item_entry['yield_expected']
        else:
            cid = item_entry
            ye = cat['yield_expected']
        name = get_name(cid)
        price = get_price(cid)
        row_num = len(rows) + 1
        item_name_rows.append(row_num)
        cap = get_item_time(cid)
        if price is None:
            rows.append([name, '가격없음', ye, '계산불가', '계산불가', cap])
        else:
            rows.append([name, price, ye, f'=B{row_num}*(400/{vpa})*{ye}', f'=B{row_num}*({vitality_cell}/{vpa})*{ye}', cap])
    data_ranges.append((cat_start, len(rows), 5))
    add_blank()

# ======================================================
# 요리
# ======================================================
add_header('요리')
craft_요리 = config['craft']['요리']
vpa = craft_요리['vitality_per_action']
lv1_ye = craft_요리['lv1_yield_expected']
lv2_ye = craft_요리['lv2_yield_expected']
add_col_header(['아이템명', 'Lv1 가격', 'Lv2 가격', '재료비', 'Lv1 수익/1제작', 'Lv2 수익/1제작', '합산수익/1제작', '생활력400 합산수익', f'생활력{vitality_cell} 합산수익'])
cat_start = len(rows) + 1
for recipe_name, recipe in craft_요리['recipes'].items():
    lv1_id = recipe.get('lv1_item')
    lv2_id = recipe.get('lv2_item')
    materials = recipe.get('materials', {})
    lv1_price = get_price(lv1_id) if lv1_id else None
    lv2_price = get_price(lv2_id) if lv2_id else None
    cap = get_item_time(lv1_id) if lv1_id else ''
    mat_cost = 0
    mat_unknown = False
    for mat_id, qty in materials.items():
        p = get_price(mat_id)
        if p is None:
            mat_unknown = True
            break
        mat_cost += p * qty
    row_num = len(rows) + 1
    item_name_rows.append(row_num)
    if mat_unknown or (lv1_price is None and lv2_price is None):
        rows.append([recipe_name, lv1_price or '가격없음', lv2_price or '가격없음', '재료가격없음', '계산불가', '계산불가', '계산불가', '계산불가', '계산불가', cap])
    else:
        lv1_rev = f'=B{row_num}*{lv1_ye}-D{row_num}' if lv1_price else '계산불가'
        lv2_rev = f'=C{row_num}*{lv2_ye}' if lv2_price else '계산불가'
        total = f'=E{row_num}+F{row_num}' if lv1_price and lv2_price else '계산불가'
        r400 = f'=G{row_num}*(400/{vpa})' if lv1_price and lv2_price else '계산불가'
        rdyn = f'=G{row_num}*({vitality_cell}/{vpa})' if lv1_price and lv2_price else '계산불가'
        rows.append([recipe_name, lv1_price or '가격없음', lv2_price or '가격없음', mat_cost, lv1_rev, lv2_rev, total, r400, rdyn, cap])
data_ranges.append((cat_start, len(rows), 9))
add_blank()

# ======================================================
# 연금술 시약/캔디
# ======================================================
add_header('연금술 (시약/캔디)')
cat_sc = config['craft']['연금술_시약캔디']
vpa = cat_sc['vitality_per_action']
lv2_ye = cat_sc['lv2_yield_expected']
lv3_ye = cat_sc['lv3_yield_expected']
add_col_header(['아이템명', 'Lv2 가격', 'Lv3 가격', 'Lv2 수익/1제작', 'Lv3 수익/1제작', '합산수익/1제작', '생활력400 합산수익', f'생활력{vitality_cell} 합산수익'])
cat_start = len(rows) + 1
for recipe_name, recipe in cat_sc['recipes'].items():
    lv2_id, lv3_id = recipe.get('lv2_item'), recipe.get('lv3_item')
    lv2_p, lv3_p = get_price(lv2_id) if lv2_id else None, get_price(lv3_id) if lv3_id else None
    cap = get_item_time(lv2_id) if lv2_id else ''
    row_num = len(rows) + 1
    item_name_rows.append(row_num)
    lv2_rev = f'=B{row_num}*{lv2_ye}' if lv2_p else '계산불가'
    lv3_rev = f'=C{row_num}*{lv3_ye}' if lv3_p else '가격없음'
    total = f'=D{row_num}+E{row_num}' if lv2_p else '계산불가'
    r400 = f'=F{row_num}*(400/{vpa})' if lv2_p else '계산불가'
    rdyn = f'=F{row_num}*({vitality_cell}/{vpa})' if lv2_p else '계산불가'
    rows.append([recipe_name, lv2_p or '가격없음', lv3_p or '가격없음', lv2_rev, lv3_rev, total, r400, rdyn, cap])
data_ranges.append((cat_start, len(rows), 8))
add_blank()

# ======================================================
# 연금술 오일
# ======================================================
add_header('연금술 (오일)')
cat_oil = config['craft']['연금술_오일']
vpa = cat_oil['vitality_per_action']
lv2_ye = cat_oil['lv2_yield_expected']
lv3_ye = cat_oil['lv3_yield_expected']
add_col_header(['아이템명', 'Lv2 가격', 'Lv3 가격', '재료비(1제작)', 'Lv2 수익/1제작', 'Lv3 수익/1제작', '합산수익/1제작', '생활력400 합산수익', f'생활력{vitality_cell} 합산수익'])
cat_start = len(rows) + 1
for recipe_name, recipe in cat_oil['recipes'].items():
    lv2_id, lv3_id = recipe.get('lv2_item'), recipe.get('lv3_item')
    materials = recipe.get('materials', {})
    lv2_p, lv3_p = get_price(lv2_id) if lv2_id else None, get_price(lv3_id) if lv3_id else None
    # 개별 레시피에 yield가 있으면 그걸 사용 (안심엘릭서 등)
    lv2_ye_item = recipe.get('lv2_yield_expected', lv2_ye)
    lv3_ye_item = recipe.get('lv3_yield_expected', lv3_ye)
    cap = get_item_time(lv2_id) if lv2_id else ''
    mat_cost = sum(get_price(mid) * qty for mid, qty in materials.items() if get_price(mid))
    mat_unknown = any(get_price(mid) is None for mid in materials)
    row_num = len(rows) + 1
    item_name_rows.append(row_num)
    if mat_unknown:
        rows.append([recipe_name, lv2_p or '가격없음', lv3_p or '가격없음', '재료가격없음', '계산불가', '계산불가', '계산불가', '계산불가', '계산불가', cap])
    else:
        lv2_rev = f'=B{row_num}*{lv2_ye_item}-D{row_num}' if lv2_p else '계산불가'
        lv3_rev = f'=C{row_num}*{lv3_ye_item}-D{row_num}' if lv3_p else '가격없음'
        total = f'=E{row_num}+F{row_num}' if lv2_p else '계산불가'
        r400 = f'=G{row_num}*(400/{vpa})' if lv2_p else '계산불가'
        rdyn = f'=G{row_num}*({vitality_cell}/{vpa})' if lv2_p else '계산불가'
        rows.append([recipe_name, lv2_p or '가격없음', lv3_p or '가격없음', mat_cost, lv2_rev, lv3_rev, total, r400, rdyn, cap])
data_ranges.append((cat_start, len(rows), 9))
add_blank()

# ======================================================
# 연금술 변환포션
# ======================================================
add_header('연금술 (변환포션)')
cat_pot = config['craft']['연금술_변환포션']
vpa = cat_pot['vitality_per_action']
ye = cat_pot['yield_expected']
add_col_header(['아이템명', '마켓가격', '재료비(1제작)', '수익/1제작', '생활력400 수익', f'생활력{vitality_cell} 수익'])
cat_start = len(rows) + 1
for recipe_name, recipe in cat_pot['recipes'].items():
    item_id = recipe.get('item')
    materials = recipe.get('materials', {})
    price = get_price(item_id) if item_id else None
    cap = get_item_time(item_id) if item_id else ''
    mat_cost = sum(get_price(mid) * qty for mid, qty in materials.items() if get_price(mid))
    mat_unknown = any(get_price(mid) is None for mid in materials)
    row_num = len(rows) + 1
    item_name_rows.append(row_num)
    if price is None or mat_unknown:
        rows.append([recipe_name, price or '가격없음', '재료가격없음', '계산불가', '계산불가', '계산불가', cap])
    else:
        rows.append([recipe_name, price, mat_cost, f'=B{row_num}*{ye}-C{row_num}', f'=D{row_num}*(400/{vpa})', f'=D{row_num}*({vitality_cell}/{vpa})', cap])
data_ranges.append((cat_start, len(rows), 6))
add_blank()

# ======================================================
# 주조
# ======================================================
add_header('주조')
add_col_header(['아이템명', '마켓가격', '재료비(1제작)', '수익/1제작', '생활력400 수익', f'생활력{vitality_cell} 수익'])
cat_start = len(rows) + 1
for subcat in ['주조_일반', '주조_일반_숙련', '주조_운석철', '주조_운석철_숙련', '주조_브리기계_기초', '주조_브리기계_숙련']:
    cat = config['craft'][subcat]
    vpa = cat['vitality_per_action']
    ye = cat['yield_expected']
    for recipe_name, recipe in cat['recipes'].items():
        item_id = recipe.get('item')
        materials = recipe.get('materials', {})
        price = get_price(item_id) if item_id else None
        cap = get_item_time(item_id) if item_id else ''
        mat_cost = 0
        mat_unknown = False
        for mid, qty in materials.items():
            p = get_price(mid)
            if p is None:
                mat_unknown = True
                break
            mat_cost += p * qty
        row_num = len(rows) + 1
        item_name_rows.append(row_num)
        display_name = f'{recipe_name}({subcat.replace("주조_","")})'
        if price is None or mat_unknown:
            rows.append([display_name, price or '가격없음', '재료가격없음', '계산불가', '계산불가', '계산불가', cap])
        else:
            rows.append([display_name, price, mat_cost, f'=B{row_num}*{ye}-C{row_num}', f'=D{row_num}*(400/{vpa})', f'=D{row_num}*({vitality_cell}/{vpa})', cap])
data_ranges.append((cat_start, len(rows), 6))
add_blank()

# ======================================================
# 공예
# ======================================================
add_header('공예')
cat = config['craft']['공예']
vpa = cat['vitality_per_action']
ye = cat['yield_expected']
lv2_ye = cat.get('lv2_yield_expected', 2.15)
add_col_header(['아이템명', '마켓가격', '재료비(1제작)', '수익/1제작', '생활력400 수익', f'생활력{vitality_cell} 수익'])
cat_start = len(rows) + 1

# Lv1 먼저 전부 출력
for recipe_name, recipe in cat['recipes'].items():
    lv1_id = recipe.get('lv1_item')
    materials = recipe.get('materials', {})
    lv1_p = get_price(lv1_id) if lv1_id else None
    cap = get_item_time(lv1_id) if lv1_id else ''
    mat_cost = 0
    mat_unknown = False
    for mid, qty in materials.items():
        p = get_price(mid)
        if p is None:
            mat_unknown = True
            break
        mat_cost += p * qty
    row_num = len(rows) + 1
    item_name_rows.append(row_num)
    if lv1_p is None or mat_unknown:
        rows.append([f'{recipe_name} Lv1', lv1_p or '가격없음', '재료가격없음', '계산불가', '계산불가', '계산불가', cap])
    else:
        rows.append([f'{recipe_name} Lv1', lv1_p, mat_cost, f'=B{row_num}*{ye}-C{row_num}', f'=D{row_num}*(400/{vpa})', f'=D{row_num}*({vitality_cell}/{vpa})', cap])

# 그 다음 Lv2 전부 출력
for recipe_name, recipe in cat['recipes'].items():
    lv2_id = recipe.get('lv2_item')
    if not lv2_id:
        continue
    lv2_materials = recipe.get('lv2_materials', {})
    lv2_p = get_price(lv2_id)
    cap2 = get_item_time(lv2_id)
    mat_cost2 = sum(get_price(mid) * qty for mid, qty in lv2_materials.items() if get_price(mid)) if lv2_materials else 0
    mat_unknown2 = any(get_price(mid) is None for mid in lv2_materials) if lv2_materials else False
    row_num2 = len(rows) + 1
    item_name_rows.append(row_num2)
    if lv2_p is None or mat_unknown2:
        rows.append([f'{recipe_name} Lv2', lv2_p or '가격없음', '재료가격없음' if mat_unknown2 else mat_cost2, '계산불가', '계산불가', '계산불가', cap2])
    else:
        rows.append([f'{recipe_name} Lv2', lv2_p, mat_cost2, f'=B{row_num2}*{lv2_ye}-C{row_num2}', f'=D{row_num2}*(400/{vpa})', f'=D{row_num2}*({vitality_cell}/{vpa})', cap2])

data_ranges.append((cat_start, len(rows), 6))
add_blank()

# ======================================================
# 직조
# ======================================================
add_header('직조')
cat = config['craft']['직조']
vpa = cat['vitality_per_action']
ye = cat['yield_expected']
add_col_header(['아이템명', '마켓가격', f'수익/1제작(기대값x{ye})', '생활력400 수익', f'생활력{vitality_cell} 수익'])
cat_start = len(rows) + 1
for recipe_name in cat['recipes']:
    price = None
    for k, v in items_db.items():
        if v.get('kor_name') == recipe_name:
            price = v.get('price')
            break
    row_num = len(rows) + 1
    item_name_rows.append(row_num)
    cap_time_item = ''
    for k, v in items_db.items():
        if v.get('kor_name') == recipe_name and v.get('updated_at'):
            try:
                from datetime import datetime as dt
                cap_time_item = dt.fromisoformat(v['updated_at']).strftime('%m-%d %H:%M')
            except:
                pass
            break
    if price is None:
        rows.append([recipe_name, '가격없음', '계산불가', '계산불가', '계산불가', cap_time_item])
    else:
        rows.append([recipe_name, price, f'=B{row_num}*{ye}', f'=C{row_num}*(400/{vpa})', f'=C{row_num}*({vitality_cell}/{vpa})', cap_time_item])
data_ranges.append((cat_start, len(rows), 5))
add_blank()

# ======================================================
# 데이터 쓰기
# ======================================================
ws.update(rows, 'A1', value_input_option='USER_ENTERED')
print(f'데이터 작성 완료: {len(rows)}행')

# ======================================================
# 데이터 쓰기
# ======================================================
ws.update(rows, 'A1', value_input_option='USER_ENTERED')
print(f'데이터 작성 완료: {len(rows)}행')
print(f'시트 URL: {sh.url}')