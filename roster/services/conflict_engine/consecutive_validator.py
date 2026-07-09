from datetime import date, timedelta
from roster.models import Roster, RosterAssignment, Conflict, RosterRule
from .assignment_validator import BaseAssignmentValidator
from .suggestion_engine import SuggestionEngine
from typing import List

class ConsecutiveValidator(BaseAssignmentValidator):
    def validate(self, roster: Roster, assignment: RosterAssignment, other_assignments: List[RosterAssignment], rules: RosterRule) -> List[Conflict]:
        conflicts = []
        employee = assignment.staff
        if not employee:
            return conflicts

        date_val = assignment.shift_date
        max_days = rules.max_consecutive_days
        
        # Pull all shift dates for this employee in adjacent range
        start_check = date_val - timedelta(days=max_days + 1)
        end_check = date_val + timedelta(days=max_days + 1)
        
        db_shifts = RosterAssignment.objects.filter(
            staff=employee,
            shift_date__range=[start_check, end_check]
        ).values_list('shift_date', flat=True)
        
        work_dates = set(db_shifts)
        work_dates.add(date_val)  # include current
        
        # Calculate streak containing date_val
        streak = 1
        check_date = date_val - timedelta(days=1)
        while check_date in work_dates:
            streak += 1
            check_date -= timedelta(days=1)
            
        check_date = date_val + timedelta(days=1)
        while check_date in work_dates:
            streak += 1
            check_date += timedelta(days=1)
            
        if streak > max_days:
            conflict = Conflict(
                id=None,
                roster=roster,
                employee=employee,
                shift=assignment.shift,
                date=date_val,
                conflict_type='MAX_CONSECUTIVE_DAYS_EXCEEDED',
                severity='High',
                status='Open'
            )
            SuggestionEngine.populate_details(conflict, assignment=assignment, meta={'streak': streak, 'limit': max_days})
            conflicts.append(conflict)
            
        return conflicts
