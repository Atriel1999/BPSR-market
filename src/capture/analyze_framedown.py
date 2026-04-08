import json, struct, zstandard as zstd
from collections import defaultdict
from datetime import datetime


def read_varint(data, pos):
    result = shift = 0
    while pos < len(data):
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
    raise ValueError(f"varint overflow at {pos}")


def parse_item_content(content):
    if len(content) == 0:
        return {}
    pos = 0
    fields = {}
    # 첫 바이트가 0x08이면 정상(field1 tag 포함), 아니면 tag 없이 바로 config_id varint
    if content[0] == 0x08:
        pos = 1
    config_id, pos = read_varint(content, pos)
    fields[1] = config_id
    while pos < len(content):
        if content[pos] == 0:
            break
        try:
            tag, pos = read_varint(content, pos)
        except:
            break
        field_num = tag >> 3
        wire_type = tag & 0x7
        if wire_type == 0:
            val, pos = read_varint(content, pos)
            fields[field_num] = val
        elif wire_type == 2:
            length, pos = read_varint(content, pos)
            fields[field_num] = content[pos:pos + length]
            pos += length
        else:
            break
    return fields


def parse_market_proto(proto):
    items = []

    # 첫 바이트 0x0a = 첫 아이템이 wire2 래퍼 없이 offset 1부터 flat하게 시작
    if proto and proto[0] == 0x0a:
        offset = 1
        fields = {}
        while offset < len(proto):
            start = offset
            try:
                tag, offset = read_varint(proto, offset)
            except:
                break
            fn = tag >> 3
            wt = tag & 0x7
            if wt != 0:
                offset = start  # wire2 태그 발견, 되돌리기
                break
            val, offset = read_varint(proto, offset)
            fields[fn] = val
        if fields.get(1):
            p = fields.get(3); q = fields.get(2)
            if isinstance(p, bytes): p = int.from_bytes(p, 'little')
            if isinstance(q, bytes): q = int.from_bytes(q, 'little')
            items.append({'config_id': fields[1], 'price': p, 'qty': q})
        proto = proto[offset:]

    # 반복 파싱 (field2 wire2 서브메시지들)
    offset = 0
    while offset < len(proto):
        try:
            tag, offset = read_varint(proto, offset)
            field_num = tag >> 3
            wire_type = tag & 0x07
            if wire_type == 2:
                length, offset = read_varint(proto, offset)
                val = proto[offset:offset + length]
                offset += length
                sub = parse_item_content(val)
                config_id = sub.get(1)
                price = sub.get(3)
                qty = sub.get(2)
                if config_id and price:
                    if isinstance(price, bytes): price = int.from_bytes(price, 'little')
                    if isinstance(qty, bytes): qty = int.from_bytes(qty, 'little')
                    items.append({'config_id': config_id, 'price': price, 'qty': qty or 0})
            elif wire_type == 0:
                _, offset = read_varint(proto, offset)
        except:
            break
    return items


def reassemble_streams(packets):
    """TCP 스트림별로 seq 기반 재조립. 서버→클라이언트 스트림만 처리."""
    from collections import defaultdict
    streams = defaultdict(list)

    for pkt in packets:
        src_ip = pkt.get('src_ip', '')
        if not (src_ip.startswith('172.') or src_ip.startswith('52.')):
            continue
        key = (pkt['src_ip'], pkt['dst_ip'], pkt['src_port'], pkt['dst_port'])
        streams[key].append(pkt)

    result = []
    for key, pkts in streams.items():
        pkts.sort(key=lambda x: x['seq'])
        isn = pkts[0]['seq']
        max_offset = max(p['seq'] - isn + p['size'] for p in pkts)
        buf = bytearray(max_offset)
        for p in pkts:
            offset = p['seq'] - isn
            raw = bytes.fromhex(p['hex'])
            buf[offset:offset + len(raw)] = raw
        result.append({'src_ip': key[0], 'data': bytes(buf)})

    return result


def parse_stream(stream_data, dctx):
    """재조립된 스트림에서 마켓 아이템 파싱"""
    items = []
    data = stream_data
    offset = 0
    while offset + 6 <= len(data):
        try:
            length = struct.unpack('>I', data[offset:offset+4])[0]
            type_raw = struct.unpack('>H', data[offset+4:offset+6])[0]
            is_compressed = (type_raw & 0x8000) != 0
            msg_type = type_raw & 0x7FFF

            # 유효하지 않은 length면 1바이트씩 이동
            if length == 0 or length > 4 * 1024 * 1024 or msg_type not in [5, 6]:
                offset += 1
                continue

            end = offset + 6 + length
            if end > len(data):
                # 데이터 부족 - 스트림 끝
                break

            payload = data[offset+6:end]

            if msg_type == 6:
                if is_compressed:
                    try:
                        inner = dctx.decompress(payload[4:], max_output_size=4 * 1024 * 1024)
                    except:
                        offset += 1
                        continue
                else:
                    inner = payload

                inner_offset = 0
                while inner_offset + 6 <= len(inner):
                    ilen = struct.unpack('>I', inner[inner_offset:inner_offset+4])[0]
                    if ilen == 0:
                        break
                    itype = struct.unpack('>H', inner[inner_offset+4:inner_offset+6])[0] & 0x7FFF
                    ipayload = inner[inner_offset+6:inner_offset+6+ilen]
                    inner_offset += 6 + ilen

                    if (itype == 3 or itype == 0) and len(ipayload) >= 16:
                        proto = ipayload[16:]
                        parsed = parse_market_proto(proto)
                        items.extend(parsed)

            offset = end
        except:
            offset += 1

    return items


def main(json_file='market_packets.json'):
    with open(json_file) as f:
        data = json.load(f)

    dctx = zstd.ZstdDecompressor()
    all_items = []

    # TCP 스트림 재조립 후 파싱
    streams = reassemble_streams(data['packets'])
    for stream in streams:
        items = parse_stream(stream['data'], dctx)
        all_items.extend(items)

    ITEMS_FILE = 'data/items.json'
    import os
    if os.path.exists(ITEMS_FILE):
        with open(ITEMS_FILE, 'r', encoding='utf-8') as f:
            items_db = json.load(f)
    else:
        print("❌ items.json 없음. convert_items.py 먼저 실행하세요.")
        return

    updated_count = 0
    updated_items = []
    unknown_count = 0
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today = datetime.now().strftime('%Y-%m-%d')

    seen = {}
    for item in all_items:
        seen[item['config_id']] = item
    all_items = list(seen.values())

    for item in all_items:
        if not isinstance(item['config_id'], int):
            continue
        cid = str(item['config_id'])

        if cid in items_db:
            entry = items_db[cid]
            old_price = entry.get('price')

            # 히스토리 업데이트 (오늘 날짜면 덮어쓰기, 새 날짜면 추가)
            history = entry.get('history', [])
            new_record = {'date': today, 'price': item['price'], 'qty': item['qty']}
            if history and history[-1]['date'] == today:
                history[-1] = new_record
            else:
                history.append(new_record)

            entry['history'] = history
            entry['price'] = item['price']
            entry['qty'] = item['qty']
            entry['updated_at'] = now

            updated_count += 1
            updated_items.append(items_db[cid].get('kor_name', cid))
            if old_price != item['price']:
                name = items_db[cid].get('kor_name', cid)
                if name not in updated_items:
                    updated_items.append(name)
        else:
            unknown_count += 1

    import shutil
    shutil.copy(ITEMS_FILE, ITEMS_FILE + '.bak')
    tmp_file = ITEMS_FILE + '.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(items_db, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, ITEMS_FILE)

    # 현황 집계
    total = len(items_db)
    has_price = sum(1 for v in items_db.values() if v.get('price') is not None)

    print(f"\n{'=' * 40}")
    print(f"  이번 캡처 결과")
    print(f"{'=' * 40}")
    print(f"  가격 업데이트:  {updated_count}개")
    print(f"  매핑 없어 무시: {unknown_count}개")
    print(f"{'=' * 40}")
    print(f"  items.json 현황")
    print(f"{'=' * 40}")
    print(f"  전체 아이템:    {total}개")
    print(f"  가격 보유:      {has_price}/{total}개")
    print(f"{'=' * 40}")

    if updated_items:
        print(f"  업데이트된 아이템 ({len(updated_items)}개):")
        for i, name in enumerate(updated_items):
            print(f"{name}", end="")
            if (i + 1) % 10 == 0:
                print()
            else:
                print(", ", end="")
        print()
        print(f"{'=' * 40}")

    # no_price = [v.get('kor_name') for v in items_db.values() if v.get('price') is None]
    # if no_price:
    #     print(f"  가격 없는 아이템 ({len(no_price)}개):")
    #     for i, name in enumerate(no_price):
    #         print(f"{name}", end="")
    #         if (i + 1) % 10 == 0:
    #             print()
    #         else:
    #             print(", ", end="")
    #     print(f"\n{'=' * 40}")

    print(f"  저장 완료: {ITEMS_FILE}")


if __name__ == '__main__':
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else 'market_packets.json')