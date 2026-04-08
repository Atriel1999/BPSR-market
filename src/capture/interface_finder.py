"""
작동하는 네트워크 인터페이스 자동 찾기
모든 패킷 캡처에서 공용으로 사용
"""
from scapy.all import sniff, get_if_list, conf
from typing import Optional
import json
from pathlib import Path


class InterfaceFinder:
    """작동하는 네트워크 인터페이스 찾기"""

    CACHE_FILE = Path.home() / ".bpsr_module" / "interface_cache.json"

    @staticmethod
    def find_working_interface(force_retest: bool = False) -> Optional[str]:
        """
        작동하는 네트워크 인터페이스 찾기

        Args:
            force_retest: 캐시 무시하고 강제로 재테스트

        Returns:
            작동하는 인터페이스 이름 또는 None
        """
        # 캐시 확인
        if not force_retest:
            cached = InterfaceFinder._load_cache()
            if cached:
                print(f"✅ 캐시된 인터페이스 사용: {cached}")
                return cached

        print("🔍 작동하는 네트워크 인터페이스 찾는 중...")
        print("   (최초 1회만, 약 10초 소요)")

        interfaces = get_if_list()

        for iface in interfaces:
            if InterfaceFinder._test_interface(iface):
                print(f"✅ 작동하는 인터페이스 발견: {iface}")
                InterfaceFinder._save_cache(iface)
                return iface

        print("❌ 작동하는 인터페이스를 찾을 수 없습니다!")
        return None

    @staticmethod
    def _test_interface(iface: str) -> bool:
        """
        특정 인터페이스가 작동하는지 테스트

        Args:
            iface: 테스트할 인터페이스

        Returns:
            작동 여부
        """
        packet_count = [0]

        def count_packet(pkt):
            packet_count[0] += 1

        try:
            # 2초 동안 또는 3개 패킷만 잡으면 성공
            sniff(
                iface=iface,
                filter="tcp",
                prn=count_packet,
                timeout=2,
                count=3,
                store=False
            )

            return packet_count[0] > 0

        except Exception:
            return False

    @staticmethod
    def _load_cache() -> Optional[str]:
        """캐시에서 인터페이스 로드"""
        if not InterfaceFinder.CACHE_FILE.exists():
            return None

        try:
            with open(InterfaceFinder.CACHE_FILE, 'r') as f:
                data = json.load(f)
                return data.get('interface')
        except:
            return None

    @staticmethod
    def _save_cache(iface: str):
        """인터페이스를 캐시에 저장"""
        InterfaceFinder.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(InterfaceFinder.CACHE_FILE, 'w') as f:
            json.dump({'interface': iface}, f)

    @staticmethod
    def setup_scapy() -> bool:
        """
        Scapy를 올바른 인터페이스로 설정

        Returns:
            성공 여부
        """
        iface = InterfaceFinder.find_working_interface()

        if not iface:
            return False

        conf.iface = iface
        return True

    @staticmethod
    def reset_cache():
        """캐시 삭제 (문제 발생 시 사용)"""
        if InterfaceFinder.CACHE_FILE.exists():
            InterfaceFinder.CACHE_FILE.unlink()
            print("✅ 캐시 삭제됨. 다음 실행 시 재테스트합니다.")


def main():
    """테스트용"""
    print("=" * 60)
    print("네트워크 인터페이스 자동 찾기 테스트")
    print("=" * 60)

    # 강제 재테스트
    iface = InterfaceFinder.find_working_interface(force_retest=True)

    if iface:
        print(f"\n✅ 성공!")
        print(f"   사용할 인터페이스: {iface}")
        print(f"   캐시 위치: {InterfaceFinder.CACHE_FILE}")
    else:
        print(f"\n❌ 실패!")
        print("가능한 원인:")
        print("  1. Npcap 서비스 미실행")
        print("  2. 관리자 권한 필요")
        print("  3. 방화벽/백신 차단")


if __name__ == "__main__":
    main()