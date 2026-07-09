from dataclasses import dataclass
from datetime import date
from typing import Dict, List
from ...models import StaffProfile, ShiftTemplate, LeaveRequest, Availability, RosterAssignment, RosterRule

@dataclass
class ScheduleContext:
    start_date: date
    end_date: date
    staff_profiles: List[StaffProfile]
    templates: Dict[str, ShiftTemplate]
    leaves_by_staff: Dict[str, List[LeaveRequest]]
    availability_by_staff: Dict[str, Availability]
    assignments_by_staff: Dict[str, List[RosterAssignment]]
    rules: RosterRule
    requirements: Dict[str, Dict[str, int]]
