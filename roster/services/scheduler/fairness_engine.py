from datetime import date
from ...models import StaffProfile
from .context import ScheduleContext

class FairnessEngine:
    def __init__(self, context: ScheduleContext):
        self.context = context
        self.staff_hours = {str(s.id): 0.0 for s in context.staff_profiles}
        self.historical_hours = {str(s.id): 0.0 for s in context.staff_profiles}
        self.staff_weekends = {str(s.id): 0 for s in context.staff_profiles}
        self._calculate_initial_stats()

    def _calculate_initial_stats(self):
        for staff in self.context.staff_profiles:
            staff_id_str = str(staff.id)
            shifts = self.context.assignments_by_staff.get(staff_id_str, [])
            for shift in shifts:
                s_date = shift.shift_date
                dur = float(shift.duration_hours)
                
                if s_date < self.context.start_date:
                    self.historical_hours[staff_id_str] += dur
                
                if self.context.start_date <= s_date <= self.context.end_date:
                    self.staff_hours[staff_id_str] += dur
                
                if s_date.weekday() >= 5:
                    self.staff_weekends[staff_id_str] += 1

    def get_workload_score(self, staff_id_str: str, max_hours: float) -> float:
        if max_hours == 0:
            return 1.0
        hours = self.staff_hours.get(staff_id_str, 0.0)
        return 1.0 - (hours / max_hours)

    def get_historical_score(self, staff_id_str: str, max_hist: float) -> float:
        if max_hist == 0:
            return 1.0
        hist = self.historical_hours.get(staff_id_str, 0.0)
        return 1.0 - (hist / max_hist)

    def get_weekend_score(self, staff_id_str: str, max_weekends: int) -> float:
        if max_weekends == 0:
            return 1.0
        weekends = self.staff_weekends.get(staff_id_str, 0)
        return 1.0 - (weekends / max_weekends)

    def get_max_hours(self) -> float:
        return max(self.staff_hours.values()) if self.staff_hours else 0.0
        
    def get_max_historical_hours(self) -> float:
        return max(self.historical_hours.values()) if self.historical_hours else 0.0
        
    def get_max_weekends(self) -> int:
        return max(self.staff_weekends.values()) if self.staff_weekends else 0

    def record_assignment(self, staff_id_str: str, duration: float, s_date: date):
        self.staff_hours[staff_id_str] += duration
        if s_date.weekday() >= 5:
            self.staff_weekends[staff_id_str] += 1
