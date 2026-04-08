"""
블루프로토콜 모듈 최적화 - 점수 계산
"""
from typing import List, Dict
from ..data.models import Module, SolverConfig, PowerCore, get_breakpoint_bonus


class ScoringCalculator:
    """점수 계산기"""
    
    def __init__(self, config: SolverConfig):
        self.config = config
    
    def calculate_combo_score(self, modules: List[Module]) -> int:
        """
        모듈 조합의 총 점수 계산
        
        점수 = Σ (스탯값 + 브레이크포인트 보너스) × 가중치
        """
        # 1. 모든 코어 합산
        total_cores = self._aggregate_cores(modules)
        
        # 2. 각 스탯별 점수 계산
        total_score = 0
        for stat_id, total_value in total_cores.items():
            stat_weight = self.config.get_stat_weight(stat_id)
            
            # 값 제한 (최대 20)
            clamped_value = min(total_value, 20)
            
            # 브레이크포인트 보너스
            breakpoint_bonus = get_breakpoint_bonus(total_value)
            
            # 점수 = (값 + 보너스) × 가중치
            score = (clamped_value + breakpoint_bonus) * stat_weight
            total_score += score
        
        return total_score
    
    def _aggregate_cores(self, modules: List[Module]) -> Dict[int, int]:
        """모듈들의 코어를 합산"""
        result = {}
        for module in modules:
            for core in module.cores:
                result[core.id] = result.get(core.id, 0) + core.value
        return result
    
    def calculate_module_score(self, module: Module) -> int:
        """단일 모듈의 점수 계산 (필터링/정렬용)"""
        score = 0
        for core in module.cores:
            stat_weight = self.config.get_stat_weight(core.id)
            score += core.value * stat_weight
        return score
    
    def meets_breakpoint_requirements(self, modules: List[Module]) -> bool:
        """
        브레이크포인트 최소 요구사항 충족 여부 확인
        """
        total_cores = self._aggregate_cores(modules)
        
        for priority in self.config.stat_priorities:
            if priority.min_level > 0:
                actual_value = total_cores.get(priority.id, 0)
                if actual_value < priority.min_level:
                    return False
        
        return True
    
    def get_stat_summary(self, modules: List[Module]) -> Dict[int, Dict]:
        """
        스탯 요약 정보 반환
        
        Returns:
            {
                stat_id: {
                    'value': 총 값,
                    'bonus': 브레이크포인트 보너스,
                    'score': 최종 점수
                }
            }
        """
        total_cores = self._aggregate_cores(modules)
        summary = {}
        
        for stat_id, total_value in total_cores.items():
            stat_weight = self.config.get_stat_weight(stat_id)
            breakpoint_bonus = get_breakpoint_bonus(total_value)
            clamped_value = min(total_value, 20)
            score = (clamped_value + breakpoint_bonus) * stat_weight
            
            summary[stat_id] = {
                'value': total_value,
                'clamped': clamped_value,
                'bonus': breakpoint_bonus,
                'weight': stat_weight,
                'score': score
            }
        
        return summary


def calculate_combat_score(modules: List[Module]) -> int:
    """
    전투력 계산 (간단한 버전)
    실제 게임 공식은 더 복잡하지만 대략적인 추정
    """
    total_cores = {}
    for module in modules:
        for core in module.cores:
            total_cores[core.id] = total_cores.get(core.id, 0) + core.value
    
    # 각 스탯의 전투력 기여도 (예시값)
    STAT_CS_MULTIPLIER = {
        # 공격 관련
        101: 50,  # 공격력
        102: 30,  # 치명타
        103: 25,  # 치명피해
        
        # 방어 관련
        201: 40,  # 방어력
        202: 35,  # HP
        
        # 기타 (기본값)
    }
    
    combat_score = 0
    for stat_id, value in total_cores.items():
        # 브레이크포인트별 강화 단계
        enhance_level = 0
        for threshold in [1, 4, 8, 12, 16, 20]:
            if value >= threshold:
                enhance_level = threshold
        
        # 스탯별 전투력 기여도
        multiplier = STAT_CS_MULTIPLIER.get(stat_id, 20)
        combat_score += enhance_level * multiplier
    
    # 전체 강화 레벨 보너스
    total_enhancement = sum(total_cores.values())
    enhancement_bonus = total_enhancement * 10
    
    return combat_score + enhancement_bonus
