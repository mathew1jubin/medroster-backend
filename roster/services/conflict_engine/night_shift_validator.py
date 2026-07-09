from datetime import date, timedelta
from roster.models import Roster, RosterAssignment, Conflict, RosterRule
from .assignment_validator import BaseAssignmentValidator
from .suggestion_engine import SuggestionEngine
from typing import List

class NightShiftValidator(BaseAssignmentValidator):
    def validate(self, roster: Roster, assignment: RosterAssignment, other_assignments: List[RosterAssignment], rules: RosterRule) -> List[Conflict]:
        conflicts = []
        
        # Only check if this assignment is a night shift
        if not assignment.shift or assignment.shift.shift_type != 'night':
            return conflicts
            
        employee = assignment.staff
        if not employee:
            return conflicts

        date_val = assignment.shift_date
        
        # Weekly check
        monday = date_val - timedelta(days=date_val.weekday())
        sunday = monday + timedelta(days=6)
        
        weekly_nights = RosterAssignment.objects.filter(
            staff=employee,
            shift__shift_type='night',
            shift_date__range=[monday, sunday]
        ).count()
        
        # RosterAssignment.objects filter might not yet include this assignment if not saved,
        # but in this context it is in memory or DB. Let's make sure count is accurate.
        # If assignment is in memory and has ID, it is already counted in query. Otherwise we add 1.
        has_id = assignment.id is not None
        if not has_id:
            weekly_nights += 1
            
        if weekly_nights > rules.max_night_per_week:
            conflict = Conflict(
                id=None,
                roster=roster,
                employee=employee,
                shift=assignment.shift,
                date=date_val,
                conflict_type='MAX_NIGHT_SHIFT_LIMIT_EXCEEDED',
                severity='High',
                status='Open'
            )
            SuggestionEngine.populate_details(conflict, assignment=assignment, meta={
                'period': 'weekly',
                'actual': weekly_nights,
                'limit': rules.max_night_per_week
            })
            conflicts.append(conflict)
            
        # Monthly check
        month_start = date_val.replace(day=1)
        next_month = month_start.replace(day=28) + timedelta(days=4)
        month_end = next_month - timedelta(days=next_month.day)
        
        monthly_nights = RosterAssignment.objects.filter(
            staff=employee,
            shift__shift_type='night',
            shift_date__range=[month_start, month_end]
        ).count()
        
        if not has_id:
            monthly_nights += 1
            
        if monthly_nights > rules.max_night_per_month:
            conflict = Conflict(
                id=None,
                roster=roster,
                employee=employee,
                shift=assignment.shift,
                date=date_val,
                conflict_type='MAX_NIGHT_SHIFT_LIMIT_EXCEEDED',
                severity='High',
                status='Open'
            )
            SuggestionEngine.populate_details(conflict, assignment=assignment, meta={
                'period': 'monthly',
                'actual': monthly_nights,
                'limit': rules.max_night_per_month
            })
            conflicts.append(conflict)

        return conflicts
