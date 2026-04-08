"""
캡처 데이터에서 미매핑 신규 아이템 config_id 추출
- items.json에서 이미 숫자 config_id로 매핑된 아이템은 제외
- season2_xxxx 같은 임시 키 아이템(미매핑)과 대조할 수 있도록 출력
"""
import json
import struct
import sys
import zstandard as zstd
from collections import defaultdict


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


def extract_all_from_capture(json_file):
    """캡처 파일에서 모든 config_id 추출 (TCP 재조립)"""
    with open(json_file) as f:
        data = json.load(f)

    dctx = zstd.ZstdDecompressor()
    found = {}

    streams = reassemble_streams(data['packets'])
    for stream in streams:
        items = parse_stream(stream['data'], dctx)
        for item in items:
            cid = item['config_id']
            found[cid] = {
                'price': item['price'],
                'qty': item['qty']
            }

    return found


def main():
    capture_file = sys.argv[1] if len(sys.argv) > 1 else 'market_packets.json'
    items_file = sys.argv[2] if len(sys.argv) > 2 else 'data/items.json'

    print(f"캡처 파일: {capture_file}")
    print(f"아이템 DB: {items_file}\n")

    # items.json에서 이미 매핑된 숫자 config_id 목록
    with open(items_file, 'r', encoding='utf-8') as f:
        items_db = json.load(f)

    known_ids = set()
    for key in items_db:
        if key.isdigit():
            known_ids.add(int(key))

    print(f"이미 매핑된 config_id: {len(known_ids)}개")

    # 캡처에서 전체 config_id 추출
    print(f"캡처 파일 파싱 중...\n")
    found = extract_all_from_capture(capture_file)

    print(f"캡처에서 발견된 전체 config_id: {len(found)}개")

    # 미매핑 필터링
    unknown = {cid: v for cid, v in found.items() if cid not in known_ids}

    print(f"미매핑 신규 config_id: {len(unknown)}개\n")

    if not unknown:
        print("미매핑 아이템 없음!")
        return

    # 출력
    print(f"{'='*55}")
    print(f"{'config_id':<12} {'price':>10} {'qty':>8}  비고(인게임에서 직접 매칭)")
    print(f"{'='*55}")
    for cid in sorted(unknown.keys()):
        v = unknown[cid]
        p = v["price"]; q = v["qty"]
        if isinstance(p, bytes): p = int.from_bytes(p, "little")
        if isinstance(q, bytes): q = int.from_bytes(q, "little")
        price_str = f"{p:,}" if p else "-"
        qty_str = f"{q:,}" if q else "-"
        print(f"{cid:<12} {price_str:>10} {qty_str:>8}")

    print(f"{'='*55}")
    print(f"\n총 {len(unknown)}개 미매핑 아이템")

    # CSV로도 저장
    output_csv = 'unknown_items.csv'
    with open(output_csv, 'w', encoding='utf-8-sig') as f:
        f.write("config_id,price,qty,kor_name,category\n")
        for cid in sorted(unknown.keys()):
            v = unknown[cid]
            f.write(f"{cid},{v['price'] or ''},{v['qty'] or ''},,\n")

    print(f"CSV 저장 완료: {output_csv} (kor_name/category 직접 채워넣으세요)")


if __name__ == '__main__':
    main()