from datetime import datetime, timedelta
from roster.models import Roster, RosterAssignment, Conflict, RosterRule
from .assignment_validator import BaseAssignmentValidator
from .suggestion_engine import SuggestionEngine
from typing import List

class DuplicateValidator(BaseAssignmentValidator):
    def validate(self, roster: Roster, assignment: RosterAssignment, other_assignments: List[RosterAssignment], rules: RosterRule) -> List[Conflict]:
        conflicts = []
        employee = assignment.staff
        if not employee:
            return conflicts

        date_val = assignment.shift_date
        
        # Compare against other assignments on the same date
        cand_start = datetime.combine(date_val, assignment.start_time)
        cand_end = cand_start + timedelta(hours=float(assignment.duration_hours))
        
        for other in other_assignments:
            if other.id == assignment.id:
                continue
            
            other_start = datetime.combine(other.shift_date, other.start_time)
            other_end = other_start + timedelta(hours=float(other.duration_hours))
            
            # Check overlap
            if cand_start < other_end and other_start < cand_end:
                is_same_shift = (assignment.shift and other.shift and assignment.shift.id == other.shift.id)
                conflict_type = 'DOUBLE_BOOKING' if is_same_shift else 'SHIFT_OVERLAP'
                
                conflict = Conflict(
                    id=None,
                    roster=roster,
                    employee=employee,
                    shift=assignment.shift,
                    date=date_val,
                    conflict_type=conflict_type,
                    severity='Critical',
                    status='Open'
                )
                SuggestionEngine.populate_details(conflict, assignment=assignment, other_assignment=other)
                conflicts.append(conflict)
                
        return conflicts
