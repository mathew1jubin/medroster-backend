import uuid
from typing import List, Dict, Set
from collections import defaultdict
from django.db import transaction
from roster.models import Roster, RosterAssignment, Conflict, RosterRule, ConflictStatus
from .leave_validator import LeaveValidator
from .duplicate_validator import DuplicateValidator
from .rest_validator import RestValidator
from .overtime_validator import OvertimeValidator
from .consecutive_validator import ConsecutiveValidator
from .night_shift_validator import NightShiftValidator
from .coverage_validator import CoverageValidator
from datetime import date

class ConflictEngineService:
    def __init__(self):
        self.validators = [
            LeaveValidator(),
            DuplicateValidator(),
            RestValidator(),
            OvertimeValidator(),
            ConsecutiveValidator(),
            NightShiftValidator()
        ]
        self.coverage_validator = CoverageValidator()

    @transaction.atomic
    def run(self, roster: Roster):
        """
        Audits a generated roster. Resolves fixed conflicts and flags new ones.
        Scans all assignments in the roster efficiently.
        """
        rules = RosterRule.objects.first()
        if not rules:
            rules = RosterRule.objects.create()

        existing_conflicts = list(Conflict.objects.filter(roster=roster))
        assignments = list(RosterAssignment.objects.filter(roster=roster).select_related('staff__user', 'shift'))
        
        # Optimize O(N^2) lookup to O(1) dictionary lookup
        assignments_by_staff = defaultdict(list)
        for a in assignments:
            assignments_by_staff[a.staff_id].append(a)
        
        detected_conflicts: List[Conflict] = []
        
        # Individual validations
        for a in assignments:
            other_assignments = assignments_by_staff[a.staff_id]
            for validator in self.validators:
                res = validator.validate(roster, a, other_assignments, rules)
                detected_conflicts.extend(res)

        # Coverage validations
        coverage_res = self.coverage_validator.validate(roster)
        detected_conflicts.extend(coverage_res)

        self._reconcile_conflicts(roster, existing_conflicts, detected_conflicts)

    @transaction.atomic
    def run_for_shift(self, roster: Roster, target_date: date, shift_type: str):
        """
        Revalidates conflicts ONLY for a specific date/shift and the employees 
        currently or previously assigned to it, avoiding full-roster queries.
        """
        rules = RosterRule.objects.first()
        if not rules:
            rules = RosterRule.objects.create()

        # 1. Fetch existing conflicts for this slot
        existing_conflicts = list(Conflict.objects.filter(
            roster=roster,
            date=target_date,
            shift__shift_type=shift_type
        ))

        # 2. Identify all affected staff
        affected_staff_ids: Set[str] = set()
        
        # Current employees assigned to this slot
        slot_assignments = list(RosterAssignment.objects.filter(
            roster=roster, shift_date=target_date, shift__shift_type=shift_type
        ).select_related('staff__user', 'shift'))
        
        for a in slot_assignments:
            if a.staff_id:
                affected_staff_ids.add(a.staff_id)
                
        # Employees who had a conflict here previously (e.g. were removed from shift)
        for c in existing_conflicts:
            if c.employee_id:
                affected_staff_ids.add(c.employee_id)

        # 3. Fetch all assignments for ONLY the affected employees
        if affected_staff_ids:
            affected_assignments = list(RosterAssignment.objects.filter(
                roster=roster, staff_id__in=affected_staff_ids
            ).select_related('staff__user', 'shift'))
        else:
            affected_assignments = []
            
        assignments_by_staff = defaultdict(list)
        for a in affected_assignments:
            assignments_by_staff[a.staff_id].append(a)

        detected_conflicts: List[Conflict] = []
        
        # Validate only the slot's active assignments
        for a in slot_assignments:
            other_assignments = assignments_by_staff[a.staff_id]
            for validator in self.validators:
                res = validator.validate(roster, a, other_assignments, rules)
                detected_conflicts.extend(res)

        # Validate coverage for the entire roster, then filter to this slot
        cov_res = self.coverage_validator.validate(roster)
        slot_cov_res = [c for c in cov_res if c.date == target_date and c.shift and c.shift.shift_type == shift_type]
        detected_conflicts.extend(slot_cov_res)

        self._reconcile_conflicts(roster, existing_conflicts, detected_conflicts)

    def _reconcile_conflicts(self, roster: Roster, existing_conflicts: List[Conflict], detected_conflicts: List[Conflict]):
        """
        Reconciles existing conflicts against newly detected conflicts using robust 
        signature arrays, preserving duplicate conflict entries accurately and updating state.
        """
        def make_signature(c: Conflict) -> str:
            emp_id = str(c.employee_id) if c.employee_id else 'none'
            shift_id = str(c.shift_id) if c.shift_id else 'none'
            date_str = c.date.strftime('%Y-%m-%d') if c.date else 'none'
            return f"{date_str}_{shift_id}_{emp_id}_{c.conflict_type}_{c.title}"

        detected_by_sig = defaultdict(list)
        for c in detected_conflicts:
            detected_by_sig[make_signature(c)].append(c)

        existing_by_sig = defaultdict(list)
        for c in existing_conflicts:
            existing_by_sig[make_signature(c)].append(c)

        to_create = []
        to_save = []

        # Process existing signatures against detected arrays
        for sig, existing_list in existing_by_sig.items():
            detected_list = detected_by_sig.get(sig, [])
            
            for i in range(len(existing_list)):
                ex = existing_list[i]
                if i < len(detected_list):
                    det = detected_list[i]
                    # Retain and update active conflict
                    if ex.status == ConflictStatus.RESOLVED:
                        ex.status = ConflictStatus.OPEN
                        ex.resolved = False
                        ex.resolved_at = None
                        
                    ex.description = det.description
                    ex.reason = det.reason
                    ex.actual_value = det.actual_value
                    ex.expected_value = det.expected_value
                    ex.suggested_resolution = det.suggested_resolution
                    to_save.append(ex)
                else:
                    # Resolve orphan conflict
                    if ex.status not in [ConflictStatus.RESOLVED, ConflictStatus.IGNORED]:
                        ex.status = ConflictStatus.RESOLVED
                        ex.resolved = True
                        to_save.append(ex)

        # Process newly detected signatures that exceed existing counts
        for sig, detected_list in detected_by_sig.items():
            existing_list = existing_by_sig.get(sig, [])
            
            for i in range(len(existing_list), len(detected_list)):
                det = detected_list[i]
                
                # Generate UUID in memory to avoid post-save secondary queries
                new_id = uuid.uuid4()
                det.id = new_id
                
                if det.planning_board_redirect and 'conflict=' not in det.planning_board_redirect:
                    det.planning_board_redirect += f"&conflict={new_id}"
                    
                to_create.append(det)

        if to_create:
            Conflict.objects.bulk_create(to_create)

        if to_save:
            for c in to_save:
                c.save()
