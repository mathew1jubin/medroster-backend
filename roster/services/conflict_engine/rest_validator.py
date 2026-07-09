from datetime import datetime, timedelta
from roster.models import Roster, RosterAssignment, Conflict, RosterRule
from .assignment_validator import BaseAssignmentValidator
from .suggestion_engine import SuggestionEngine
from typing import List

class RestValidator(BaseAssignmentValidator):
    def validate(self, roster: Roster, assignment: RosterAssignment, other_assignments: List[RosterAssignment], rules: RosterRule) -> List[Conflict]:
        conflicts = []
        employee = assignment.staff
        if not employee:
            return conflicts

        date_val = assignment.shift_date
        min_rest_hours = float(rules.minimum_rest_hours)
        
        cand_start = datetime.combine(date_val, assignment.start_time)
        cand_end = cand_start + timedelta(hours=float(assignment.duration_hours))
        
        for other in other_assignments:
            if other.id == assignment.id:
                continue
            
            other_start = datetime.combine(other.shift_date, other.start_time)
            other_end = other_start + timedelta(hours=float(other.duration_hours))
            
            gap = 0.0
            violates = False
            if other_end <= cand_start:
                gap = (cand_start - other_end).total_seconds() / 3600.0
                if gap < min_rest_hours:
                    violates = True
            elif cand_end <= other_start:
                gap = (other_start - cand_end).total_seconds() / 3600.0
                if gap < min_rest_hours:
                    violates = True
                    
            if violates:
                conflict = Conflict(
                    id=None,
                    roster=roster,
                    employee=employee,
                    shift=assignment.shift,
                    date=date_val,
                    conflict_type='REST_RULE_VIOLATION',
                    severity='High',
                    status='Open'
                )
                SuggestionEngine.populate_details(conflict, assignment=assignment, other_assignment=other, meta={'gap': gap, 'min_rest': min_rest_hours})
                conflicts.append(conflict)
                
        return conflicts
