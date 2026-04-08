"""
마켓 가격 정보 패킷 캡처
"""
import sys
from pathlib import Path
from scapy.all import sniff, TCP, IP
from datetime import datetime
import json

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.capture.process_finder import ProcessFinder
from src.capture.interface_finder import InterfaceFinder


class MarketPacketCapture:
    """마켓 패킷 캡처"""

    def __init__(self, server_ips: list[str]):
        self.server_ips = server_ips
        self.packets = []

    def _process_packet(self, packet):
        """패킷 처리"""
        if not packet.haslayer(TCP) or not packet.haslayer(IP):
            return

        tcp_layer = packet[TCP]
        ip_layer = packet[IP]

        if ip_layer.src not in self.server_ips and ip_layer.dst not in self.server_ips:
            return

        if not tcp_layer.payload:
            return

        payload = bytes(tcp_layer.payload)

        packet_info = {
            'timestamp': datetime.now().isoformat(),
            'src_ip': ip_layer.src,
            'src_port': tcp_layer.sport,
            'dst_ip': ip_layer.dst,
            'dst_port': tcp_layer.dport,
            'seq': tcp_layer.seq,
            'size': len(payload),
            'hex': payload.hex(),
            'preview': payload[:100].hex()
        }

        self.packets.append(packet_info)
        print(f"\rPackets: {len(self.packets)}", end='')

    def capture(self, duration: int):
        """캡처"""
        if self.server_ips:
            ip_filter = " or ".join([f"host {ip}" for ip in self.server_ips])
            bpf_filter = f"tcp and ({ip_filter})"
        else:
            bpf_filter = "tcp"

        print(f"🔴 캡처 시작!")
        print(f"   Duration: {duration}초\n")

        sniff(
            filter=bpf_filter,
            prn=self._process_packet,
            timeout=duration,
            store=False
        )

    def save_results(self, filename: str):
        """JSON 저장"""
        result = {
            'summary': {
                'total_packets': len(self.packets),
                'capture_time': datetime.now().isoformat()
            },
            'packets': self.packets
        }

        with open(filename, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"\n✅ Saved to: {filename}")

    def print_summary(self):
        """요약 출력"""
        print(f"\n\n{'=' * 60}")
        print(f"캡처 완료: {len(self.packets)}개 패킷")
        print(f"{'=' * 60}\n")


def main():
    print("=" * 60)
    print("마켓 가격 정보 패킷 캡처")
    print("=" * 60)

    print("\n[1/4] 네트워크 인터페이스 설정...")
    if not InterfaceFinder.setup_scapy():
        print("❌ 네트워크 인터페이스 설정 실패!")
        print("   관리자 권한으로 실행하세요.")
        return
    print("✅ 완료")

    print("\n[2/4] 게임 프로세스 찾기...")
    game_process = ProcessFinder.find_game_process()
    if not game_process:
        print("❌ 게임이 실행되지 않았습니다!")
        return
    print("✅ 완료")

    print("\n[3/4] 게임 서버 IP 확인...")
    server_ips = ProcessFinder.get_game_server_ips()
    if not server_ips:
        print("❌ 게임 서버 연결 없음!")
        return
    print(f"✅ Server IPs: {server_ips}")

    print("\n[4/4] 패킷 캡처 준비")
    print("=" * 60)
    print("📋 준비사항:")
    print("   1. 게임 마켓 UI 열기")
    print("   2. 아이템 검색하기")
    print("   3. 검색 결과 확인")
    print("=" * 60)
    input("\n준비되면 ENTER를 누르세요...\n")

    print("🔴 지금 마켓에서 아이템을 검색하세요!\n")

    capture = MarketPacketCapture(server_ips)
    capture.capture(duration=600)

    capture.print_summary()
    capture.save_results("market_packets.json")

    print("\n💡 다음 단계:")
    print("   python analyze_framedown.py market_packets.json")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 중단됨")
    except Exception as e:
        print(f"\n❌ 에러: {e}")
        import traceback
        traceback.print_exc()