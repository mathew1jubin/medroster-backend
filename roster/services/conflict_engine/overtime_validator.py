from datetime import date, timedelta
from roster.models import Roster, RosterAssignment, Conflict, RosterRule
from .assignment_validator import BaseAssignmentValidator
from .suggestion_engine import SuggestionEngine
from typing import List

class OvertimeValidator(BaseAssignmentValidator):
    def validate(self, roster: Roster, assignment: RosterAssignment, other_assignments: List[RosterAssignment], rules: RosterRule) -> List[Conflict]:
        conflicts = []
        employee = assignment.staff
        if not employee:
            return conflicts

        date_val = assignment.shift_date
        
        # Calculate daily hours
        daily_hours = float(assignment.duration_hours)
        for other in other_assignments:
            if other.id != assignment.id and other.shift_date == date_val:
                daily_hours += float(other.duration_hours)
                
        if daily_hours > float(rules.max_hours_per_day):
            conflict = Conflict(
                id=None,
                roster=roster,
                employee=employee,
                shift=assignment.shift,
                date=date_val,
                conflict_type='OVERTIME_LIMIT_EXCEEDED',
                severity='High',
                status='Open'
            )
            SuggestionEngine.populate_details(conflict, assignment=assignment, meta={
                'period': 'daily',
                'actual': daily_hours,
                'limit': float(rules.max_hours_per_day)
            })
            conflicts.append(conflict)
            
        # Calculate weekly hours (Monday to Sunday)
        monday = date_val - timedelta(days=date_val.weekday())
        sunday = monday + timedelta(days=6)
        
        # Query all assignments in this week from database to include history not in memory
        weekly_assignments = RosterAssignment.objects.filter(
            staff=employee,
            shift_date__range=[monday, sunday]
        )
        
        weekly_hours = 0.0
        for s in weekly_assignments:
            if s.id == assignment.id:
                weekly_hours += float(assignment.duration_hours)
            else:
                weekly_hours += float(s.duration_hours)
                
        if weekly_hours > float(rules.max_hours_per_week):
            conflict = Conflict(
                id=None,
                roster=roster,
                employee=employee,
                shift=assignment.shift,
                date=date_val,
                conflict_type='OVERTIME_LIMIT_EXCEEDED',
                severity='High',
                status='Open'
            )
            SuggestionEngine.populate_details(conflict, assignment=assignment, meta={
                'period': 'weekly',
                'actual': weekly_hours,
                'limit': float(rules.max_hours_per_week)
            })
            conflicts.append(conflict)
            
        # Calculate monthly hours
        month_start = date_val.replace(day=1)
        next_month = month_start.replace(day=28) + timedelta(days=4)
        month_end = next_month - timedelta(days=next_month.day)
        
        monthly_assignments = RosterAssignment.objects.filter(
            staff=employee,
            shift_date__range=[month_start, month_end]
        )
        
        monthly_hours = 0.0
        for s in monthly_assignments:
            if s.id == assignment.id:
                monthly_hours += float(assignment.duration_hours)
            else:
                monthly_hours += float(s.duration_hours)
                
        if monthly_hours > float(rules.max_hours_per_month):
            conflict = Conflict(
                id=None,
                roster=roster,
                employee=employee,
                shift=assignment.shift,
                date=date_val,
                conflict_type='OVERTIME_LIMIT_EXCEEDED',
                severity='High',
                status='Open'
            )
            SuggestionEngine.populate_details(conflict, assignment=assignment, meta={
                'period': 'monthly',
                'actual': monthly_hours,
                'limit': float(rules.max_hours_per_month)
            })
            conflicts.append(conflict)

        return conflicts
