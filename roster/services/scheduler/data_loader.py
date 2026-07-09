from datetime import date, timedelta
from typing import Dict
from ...models import StaffProfile, ShiftTemplate, LeaveRequest, Availability, RosterAssignment, RosterRule
from .context import ScheduleContext

class DataLoader:
    def load(self, start_date: date, end_date: date, requirements: Dict[str, Dict[str, int]]) -> ScheduleContext:
        staff_profiles = list(StaffProfile.objects.exclude(user__role='manager').select_related('user'))
        
        rules = RosterRule.objects.first()
        if not rules:
            rules = RosterRule.objects.create()

        templates = self._get_or_create_templates()

        approved_leaves = list(LeaveRequest.objects.filter(
            status='Approved',
            start_date__lte=end_date,
            end_date__gte=start_date
        ))
        
        leaves_by_staff = {str(staff.id): [] for staff in staff_profiles}
        for l in approved_leaves:
            staff_id_str = str(l.staff_id)
            if staff_id_str not in leaves_by_staff:
                leaves_by_staff[staff_id_str] = []
            leaves_by_staff[staff_id_str].append(l)

        availabilities = list(Availability.objects.filter(staff__in=staff_profiles))
        availability_by_staff = {str(a.staff_id): a for a in availabilities}

        existing_assignments = list(RosterAssignment.objects.filter(
            shift_date__range=[start_date - timedelta(days=30), end_date + timedelta(days=7)]
        ).select_related('shift'))

        assignments_by_staff = {str(staff.id): [] for staff in staff_profiles}
        for s in existing_assignments:
            staff_id_str = str(s.staff_id)
            if staff_id_str in assignments_by_staff:
                assignments_by_staff[staff_id_str].append(s)

        return ScheduleContext(
            start_date=start_date,
            end_date=end_date,
            staff_profiles=staff_profiles,
            templates=templates,
            leaves_by_staff=leaves_by_staff,
            availability_by_staff=availability_by_staff,
            assignments_by_staff=assignments_by_staff,
            rules=rules,
            requirements=requirements
        )

    def _get_or_create_templates(self) -> Dict[str, ShiftTemplate]:
        from datetime import time
        templates = {}
        for s_type in ['morning', 'evening', 'night']:
            template = ShiftTemplate.objects.filter(shift_type=s_type).first()
            if not template:
                if s_type == 'morning':
                    start_t, end_t, dur = time(7, 0, 0), time(15, 0, 0), 8.0
                elif s_type == 'evening':
                    start_t, end_t, dur = time(15, 0, 0), time(23, 0, 0), 8.0
                else:
                    start_t, end_t, dur = time(23, 0, 0), time(7, 0, 0), 8.0
                template = ShiftTemplate.objects.create(
                    name=f"{s_type.capitalize()} Shift",
                    start_time=start_t,
                    end_time=end_t,
                    duration_hours=dur,
                    shift_type=s_type,
                    color='#3B82F6' if s_type == 'morning' else '#8B5CF6' if s_type == 'evening' else '#1E293B'
                )
            templates[s_type] = template
        return templates
