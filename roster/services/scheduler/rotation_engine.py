from datetime import date
from ...models import StaffProfile, ShiftTemplate
from .context import ScheduleContext

class RotationEngine:
    def __init__(self, context: ScheduleContext):
        self.context = context
        self.last_shift_type = {}
        self._initialize()

    def _initialize(self):
        for staff in self.context.staff_profiles:
            staff_id_str = str(staff.id)
            shifts = self.context.assignments_by_staff.get(staff_id_str, [])
            recent_shifts = sorted([s for s in shifts if s.shift_date < self.context.start_date], key=lambda s: s.shift_date, reverse=True)
            if recent_shifts and recent_shifts[0].shift:
                self.last_shift_type[staff_id_str] = recent_shifts[0].shift.shift_type
            else:
                self.last_shift_type[staff_id_str] = None

    def get_rotation_bonus(self, staff_id_str: str, candidate_type: str) -> float:
        last_type = self.last_shift_type.get(staff_id_str)
        if not last_type:
            return 0.0
            
        if last_type == 'morning' and candidate_type == 'evening':
            return 0.5
        elif last_type == 'evening' and candidate_type == 'night':
            return 0.5
        elif last_type == 'night' and candidate_type == 'morning':
            return 0.5
            
        return 0.0

    def record_assignment(self, staff_id_str: str, candidate_type: str):
        self.last_shift_type[staff_id_str] = candidate_type
