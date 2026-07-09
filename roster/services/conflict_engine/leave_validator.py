from roster.models import Roster, RosterAssignment, Conflict, RosterRule, LeaveRequest
from .assignment_validator import BaseAssignmentValidator
from .suggestion_engine import SuggestionEngine
from typing import List

class LeaveValidator(BaseAssignmentValidator):
    def validate(self, roster: Roster, assignment: RosterAssignment, other_assignments: List[RosterAssignment], rules: RosterRule) -> List[Conflict]:
        conflicts = []
        employee = assignment.staff
        if not employee:
            return conflicts

        # Find approved leaves for this employee on this date
        date_val = assignment.shift_date
        has_leave = LeaveRequest.objects.filter(
            staff=employee,
            status='Approved',
            start_date__lte=date_val,
            end_date__gte=date_val
        ).exists()

        if has_leave:
            conflict = Conflict(
                id=None,  # Will be saved or populated in engine
                roster=roster,
                employee=employee,
                shift=assignment.shift,
                date=date_val,
                conflict_type='LEAVE_VIOLATION',
                severity='Critical',
                status='Open'
            )
            SuggestionEngine.populate_details(conflict, assignment=assignment)
            conflicts.append(conflict)

        return conflicts
