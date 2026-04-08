"""
매핑 확인된 config_id를 items.json에 반영하는 스크립트

사용법:
    python map_config_ids.py items.json

동작:
    - MAPPINGS 딕셔너리에 정의된 config_id → 아이템 정보를 items.json에 추가
    - 기존 season2_xxxx 임시 키 항목 중 kor_name이 일치하는 항목은 자동으로 제거
    - 백업 파일(items.json.bak) 자동 생성
"""
import json
import shutil
import sys
from datetime import datetime

# ======================================================
# 여기에 매핑 추가하면 됨
# config_id: { kor_name, eng_name, category, season }
# ======================================================
MAPPINGS = {
    # 식물학 시즌2
    1092085: {"kor_name": "남풍고추",   "eng_name": "", "category": "식물학", "season": 2},
    1092086: {"kor_name": "빗방울콩",   "eng_name": "", "category": "식물학", "season": 2},
    1092087: {"kor_name": "바위엉겅퀴", "eng_name": "", "category": "식물학", "season": 2},
    # 목공 시즌2
    1080005: {"kor_name": "고열석골숯가루", "eng_name": "", "category": "목공", "season": 2},
    # 요리 시즌2 신규
    1082108: {"kor_name": "비법풍미염장갈비", "eng_name": "", "category": "요리", "season": 2},
    1082118: {"kor_name": "진미절인생선",     "eng_name": "", "category": "요리", "season": 2},
    1012293: {"kor_name": "황금더블미트버거 Lv1",       "eng_name": "", "category": "요리", "season": 2},
    1012294: {"kor_name": "황금더블미트버거 Lv2",       "eng_name": "", "category": "요리", "season": 2},
    1012303: {"kor_name": "더블호화스튜 Lv1",           "eng_name": "", "category": "요리", "season": 2},
    1012304: {"kor_name": "더블호화스튜 Lv2",           "eng_name": "", "category": "요리", "season": 2},
    1012313: {"kor_name": "매콤향신생선구이 Lv1",       "eng_name": "", "category": "요리", "season": 2},
    1012314: {"kor_name": "매콤향신생선구이 Lv2",       "eng_name": "", "category": "요리", "season": 2},
    1012323: {"kor_name": "따듯한바람해물수프 Lv1",     "eng_name": "", "category": "요리", "season": 2},
    1012324: {"kor_name": "따듯한바람해물수프 Lv2",     "eng_name": "", "category": "요리", "season": 2},
    1012333: {"kor_name": "담백염장생선꼬치 Lv1",       "eng_name": "", "category": "요리", "season": 2},
    1012334: {"kor_name": "담백염장생선꼬치 Lv2",       "eng_name": "", "category": "요리", "season": 2},
    1012343: {"kor_name": "괴상한빗방울콩퓌레 Lv1",     "eng_name": "", "category": "요리", "season": 2},
    1012344: {"kor_name": "괴상한빗방울콩퓌레 Lv2",     "eng_name": "", "category": "요리", "season": 2},
    1012353: {"kor_name": "화염고추향갈비 Lv1",         "eng_name": "", "category": "요리", "season": 2},
    1012354: {"kor_name": "화염고추향갈비 Lv2",         "eng_name": "", "category": "요리", "season": 2},
    1012363: {"kor_name": "작열매운갈비 Lv1",           "eng_name": "", "category": "요리", "season": 2},
    1012364: {"kor_name": "작열매운갈비 Lv2",           "eng_name": "", "category": "요리", "season": 2},
    1012373: {"kor_name": "라팔마을전원솥요리 Lv1",     "eng_name": "", "category": "요리", "season": 2},
    1012374: {"kor_name": "라팔마을전원솥요리 Lv2",     "eng_name": "", "category": "요리", "season": 2},
    1012383: {"kor_name": "고원특선모듬찜 Lv1",         "eng_name": "", "category": "요리", "season": 2},
    1012384: {"kor_name": "고원특선모듬찜 Lv2",         "eng_name": "", "category": "요리", "season": 2},
    1012393: {"kor_name": "지글지글염장생선구이 Lv1",   "eng_name": "", "category": "요리", "season": 2},
    1012394: {"kor_name": "지글지글염장생선구이 Lv2",   "eng_name": "", "category": "요리", "season": 2},
    1012403: {"kor_name": "지글지글갈비구이 Lv1",       "eng_name": "", "category": "요리", "season": 2},
    1012404: {"kor_name": "지글지글갈비구이 Lv2",       "eng_name": "", "category": "요리", "season": 2},
    1012413: {"kor_name": "순한풍미소스 Lv1",           "eng_name": "", "category": "요리", "season": 2},
    1012414: {"kor_name": "순한풍미소스 Lv2",           "eng_name": "", "category": "요리", "season": 2},
    1012423: {"kor_name": "눈꽃치즈꿀콩롤 Lv1",         "eng_name": "", "category": "요리", "season": 2},
    1012424: {"kor_name": "눈꽃치즈꿀콩롤 Lv2",         "eng_name": "", "category": "요리", "season": 2},
    # 비법풍미염장갈비, 진미절인생선 보류
}

def main():
    items_file = sys.argv[1] if len(sys.argv) > 1 else 'data/items.json'

    # 백업
    backup_file = items_file + '.bak'
    shutil.copy2(items_file, backup_file)
    print(f"백업 생성: {backup_file}")

    with open(items_file, 'r', encoding='utf-8') as f:
        items_db = json.load(f)

    added = 0
    skipped = 0
    removed_temp = 0

    for config_id, info in MAPPINGS.items():
        key = str(config_id)

        # 이미 있으면 스킵
        if key in items_db:
            print(f"⏭️  {key} 이미 존재, 스킵")
            skipped += 1
            continue

        # lv 정보를 kor_name에 반영
        kor_name = info['kor_name']

        # 신규 추가
        items_db[key] = {
            "kor_name": kor_name,
            "eng_name": info.get('eng_name', ''),
            "category": info.get('category', ''),
            "season": info.get('season', 2),
            "price": None,
            "qty": None,
            "history": [],
            "updated_at": None
        }
        print(f"✅ 추가: {key} → {kor_name}")
        added += 1

    # season2_xxxx 임시 키 중 매핑된 kor_name(Lv 제외)과 일치하는 항목 제거
    mapped_names = set(info['kor_name'] for info in MAPPINGS.values())
    temp_keys_to_remove = []
    for key, val in items_db.items():
        if key.startswith('season2_') and val.get('kor_name') in mapped_names:
            temp_keys_to_remove.append(key)

    for key in temp_keys_to_remove:
        print(f"🗑️  임시 키 제거: {key} ({items_db[key]['kor_name']})")
        del items_db[key]
        removed_temp += 1

    with open(items_file, 'w', encoding='utf-8') as f:
        json.dump(items_db, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*40}")
    print(f"  추가: {added}개")
    print(f"  스킵: {skipped}개")
    print(f"  임시키 제거: {removed_temp}개")
    print(f"  저장 완료: {items_file}")
    print(f"{'='*40}")


if __name__ == '__main__':
    main()