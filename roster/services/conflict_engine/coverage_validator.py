from roster.models import Roster, RosterAssignment, Conflict, ShiftTemplate
from .suggestion_engine import SuggestionEngine
from typing import List, Dict
from datetime import timedelta

class CoverageValidator:
    def _normalize_role_name(self, role_name: str) -> str:
        from roster.models import ClinicalRole
        if role_name in ['Doctors', 'Doctor']:
            return ClinicalRole.DOCTOR
        elif role_name in ['Nurses', 'Nurse']:
            return ClinicalRole.NURSE
        elif role_name in ['Staff', 'Support Staff']:
            return ClinicalRole.SUPPORT_STAFF
        return ClinicalRole.NURSE

    def validate(self, roster: Roster) -> List[Conflict]:
        conflicts = []
        
        # Load all roster assignments
        assignments = list(RosterAssignment.objects.filter(roster=roster).select_related('staff', 'shift'))
        
        # Use requirements saved in Roster, or fallback
        requirements = roster.requirements
        if not requirements:
            requirements = {
                'morning': {'Doctor': 2, 'Nurse': 4, 'Support Staff': 2},
                'evening': {'Doctor': 2, 'Nurse': 3, 'Support Staff': 2},
                'night': {'Doctor': 1, 'Nurse': 2, 'Support Staff': 1},
            }
            
        # Group assignments by date and shift template
        grouped: Dict[tuple, List[RosterAssignment]] = {}
        current_day = roster.start_date
        while current_day <= roster.end_date:
            for s_type in ['morning', 'evening', 'night']:
                grouped[(current_day, s_type)] = []
            current_day += timedelta(days=1)
            
        for a in assignments:
            if not a.shift:
                continue
            s_type = a.shift.shift_type
            key = (a.shift_date, s_type)
            if key in grouped:
                grouped[key].append(a)
                
        # Audit each slot
        for (date_val, s_type), slot_assignments in grouped.items():
            reqs = requirements.get(s_type, {})
            if not reqs:
                continue
                
            # Count current roles
            role_counts = {'Doctor': 0, 'Nurse': 0, 'Support Staff': 0}
            for a in slot_assignments:
                if a.staff:
                    role_counts[a.staff.role] = role_counts.get(a.staff.role, 0) + 1
                    
            understaffed_roles = []
            overstaffed_roles = []
            
            for raw_role, required in reqs.items():
                role = self._normalize_role_name(raw_role)
                actual = role_counts.get(role, 0)
                if actual < required:
                    understaffed_roles.append((role, required, actual))
                elif actual > required:
                    overstaffed_roles.append((role, required, actual))
                    
            template = ShiftTemplate.objects.filter(shift_type=s_type).first()
            
            # Group understaffed -> Now one per role!
            for role, req, act in understaffed_roles:
                conflict = Conflict(
                    id=None,
                    roster=roster,
                    employee=None,
                    shift=template,
                    date=date_val,
                    conflict_type='UNDERSTAFFED_SHIFT',
                    severity='High',
                    status='Open'
                )
                SuggestionEngine.populate_details(conflict, meta={
                    'roles': [(role, req, act)],
                    'shift_name': s_type.capitalize()
                })
                conflicts.append(conflict)
                
            # Group overstaffed -> Now one per role!
            for role, req, act in overstaffed_roles:
                conflict = Conflict(
                    id=None,
                    roster=roster,
                    employee=None,
                    shift=template,
                    date=date_val,
                    conflict_type='OVERSTAFFED_SHIFT',
                    severity='Medium',
                    status='Open'
                )
                SuggestionEngine.populate_details(conflict, meta={
                    'roles': [(role, req, act)],
                    'shift_name': s_type.capitalize()
                })
                conflicts.append(conflict)
                
        return conflicts
