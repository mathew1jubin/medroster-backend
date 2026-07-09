import random
from datetime import date, datetime, timedelta
from ...models import StaffProfile, ShiftTemplate
from .context import ScheduleContext
from .fairness_engine import FairnessEngine
from .rotation_engine import RotationEngine

class ScoringEngine:
    def __init__(self, context: ScheduleContext, fairness: FairnessEngine, rotation: RotationEngine):
        self.context = context
        self.fairness = fairness
        self.rotation = rotation

    def score(self, staff: StaffProfile, current_day: date, template: ShiftTemplate) -> float:
        staff_id_str = str(staff.id)
        
        max_hours = self.fairness.get_max_hours()
        max_hist = self.fairness.get_max_historical_hours()
        max_weekends = self.fairness.get_max_weekends()

        score_workload = self.fairness.get_workload_score(staff_id_str, max_hours)
        score_hist = self.fairness.get_historical_score(staff_id_str, max_hist)
        score_weekend = self.fairness.get_weekend_score(staff_id_str, max_weekends)

        pref_score = 0.0
        avail = self.context.availability_by_staff.get(staff_id_str)
        if avail:
            if avail.preferred_shift == template.shift_type:
                pref_score += 1.0
            day_name = current_day.strftime('%a')
            if avail.preferred_days_off and day_name not in avail.preferred_days_off:
                pref_score += 0.5
                
        rot_bonus = self.rotation.get_rotation_bonus(staff_id_str, template.shift_type)
        pref_score += rot_bonus

        rest_score = self._calculate_rest_score(staff_id_str, current_day, template)

        final_score = (
            (0.35 * score_workload) +
            (0.25 * min(pref_score / 2.0, 1.0)) +
            (0.15 * rest_score) +
            (0.10 * score_weekend) +
            (0.10 * score_hist) +
            (0.05 * random.random())
        )
        return final_score

    def _calculate_rest_score(self, staff_id_str: str, current_day: date, template: ShiftTemplate) -> float:
        cand_start = datetime.combine(current_day, template.start_time)
        cand_end = cand_start + timedelta(hours=float(template.duration_hours))
        
        shifts = self.context.assignments_by_staff.get(staff_id_str, [])
        min_rest = float('inf')
        
        for shift in shifts:
            s_start = datetime.combine(shift.shift_date, shift.start_time)
            s_end = s_start + timedelta(hours=float(shift.duration_hours))
            
            if s_end <= cand_start:
                gap = (cand_start - s_end).total_seconds() / 3600.0
                if gap < min_rest:
                    min_rest = gap
            elif cand_end <= s_start:
                gap = (s_start - cand_end).total_seconds() / 3600.0
                if gap < min_rest:
                    min_rest = gap

        if min_rest == float('inf'):
            return 1.0
            
        req_rest = float(self.context.rules.minimum_rest_hours)
        if min_rest <= req_rest:
            return 0.0
            
        capped_rest = min(min_rest, 24.0)
        return (capped_rest - req_rest) / max((24.0 - req_rest), 1.0)
