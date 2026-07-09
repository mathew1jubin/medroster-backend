from datetime import date
from typing import List
from ...models import Roster, RosterAssignment, StaffProfile, ShiftTemplate
from .context import ScheduleContext
from .fairness_engine import FairnessEngine
from .rotation_engine import RotationEngine

class AssignmentEngine:
    def __init__(self, context: ScheduleContext, fairness: FairnessEngine, rotation: RotationEngine):
        self.context = context
        self.fairness = fairness
        self.rotation = rotation
        self.created_shifts: List[RosterAssignment] = []

    def create_assignment(self, roster: Roster, staff: StaffProfile, current_day: date, template: ShiftTemplate) -> RosterAssignment:
        shift = RosterAssignment(
            roster=roster,
            staff=staff,
            shift=template,
            shift_date=current_day,
            start_time=template.start_time,
            end_time=template.end_time,
            duration_hours=template.duration_hours,
            status='Scheduled'
        )
        self.created_shifts.append(shift)
        
        staff_id_str = str(staff.id)
        self.context.assignments_by_staff[staff_id_str].append(shift)
        self.fairness.record_assignment(staff_id_str, float(template.duration_hours), current_day)
        self.rotation.record_assignment(staff_id_str, template.shift_type)
        
        return shift
