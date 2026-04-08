"""
블루프로토콜 게임 프로세스 찾기
"""
import psutil
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TcpConnection:
    """TCP 연결 정보"""
    local_addr: str
    local_port: int
    remote_addr: str
    remote_port: int
    status: str
    
    def __repr__(self):
        return f"{self.local_addr}:{self.local_port} -> {self.remote_addr}:{self.remote_port} ({self.status})"


class ProcessFinder:
    """게임 프로세스 찾기"""
    
    GAME_PROCESS_NAMES = ['StarASIA.exe', 'StarASIA_STEAM.exe']
    
    @staticmethod
    def find_game_process() -> Optional[psutil.Process]:
        """
        블루프로토콜 게임 프로세스 찾기
        
        Returns:
            게임 프로세스 또는 None
        """
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'] in ProcessFinder.GAME_PROCESS_NAMES:
                    print(f"✅ 게임 프로세스 발견: {proc.info['name']} (PID: {proc.info['pid']})")
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return None
    
    @staticmethod
    def get_tcp_connections(process: psutil.Process) -> List[TcpConnection]:
        """
        프로세스의 TCP 연결 목록 가져오기
        
        Args:
            process: 대상 프로세스
            
        Returns:
            TCP 연결 리스트
        """
        connections = []
        
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.pid == process.pid:
                # TCP만, ESTABLISHED 상태만
                    if conn.type == 1 and conn.status == 'ESTABLISHED':  # type 1 = SOCK_STREAM (TCP)
                        if conn.raddr:  # remote address 있는 경우만
                            tcp_conn = TcpConnection(
                                local_addr=conn.laddr.ip,
                                local_port=conn.laddr.port,
                                remote_addr=conn.raddr.ip,
                                remote_port=conn.raddr.port,
                                status=conn.status
                            )
                            connections.append(tcp_conn)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"⚠️ 연결 정보 가져오기 실패: {e}")
        
        return connections
    
    @staticmethod
    def get_game_server_ips() -> List[str]:
        """
        게임 서버 IP 목록 반환 (패킷 필터용)
        
        Returns:
            게임 서버 IP 리스트
        """
        process = ProcessFinder.find_game_process()
        if not process:
            return []
        
        connections = ProcessFinder.get_tcp_connections(process)
        
        # 포트 1000 이상인 연결만 (게임 서버)
        server_ips = set()
        for conn in connections:
            if conn.remote_port > 1000:
                server_ips.add(conn.remote_addr)
        
        return list(server_ips)
    
    @staticmethod
    def wait_for_game(check_interval: int = 2) -> psutil.Process:
        """
        게임 실행될 때까지 대기
        
        Args:
            check_interval: 확인 간격 (초)
            
        Returns:
            게임 프로세스
        """
        import time
        
        print("🎮 블루프로토콜 게임을 실행하고 대기 중...")
        
        while True:
            proc = ProcessFinder.find_game_process()
            if proc:
                return proc
            
            time.sleep(check_interval)


def main():
    """테스트용 메인 함수"""
    print("=" * 50)
    print("블루프로토콜 프로세스 찾기 테스트")
    print("=" * 50)
    
    # 게임 프로세스 찾기
    proc = ProcessFinder.find_game_process()
    
    if not proc:
        print("❌ 게임이 실행되지 않았습니다.")
        print("게임을 실행하고 다시 시도하세요.")
        return
    
    # TCP 연결 정보
    connections = ProcessFinder.get_tcp_connections(proc)
    
    print(f"\n📡 TCP 연결: {len(connections)}개")
    print("-" * 50)
    
    for i, conn in enumerate(connections, 1):
        print(f"{i}. {conn}")
    
    # 게임 서버 IP
    server_ips = ProcessFinder.get_game_server_ips()
    print(f"\n🎮 게임 서버 IP: {server_ips}")
    print("=" * 50)


if __name__ == '__main__':
    main()
