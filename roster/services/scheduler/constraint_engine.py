from datetime import date, datetime, timedelta
from typing import Tuple
from ...models import StaffProfile, ShiftTemplate
from .context import ScheduleContext

class ConstraintEngine:
    def evaluate(self, staff: StaffProfile, current_day: date, template: ShiftTemplate, context: ScheduleContext) -> Tuple[bool, int]:
        """
        Evaluates HARD and SOFT constraints.
        Returns (is_hard_valid, soft_violation_count).
        If is_hard_valid is False, the candidate cannot be scheduled.
        If is_hard_valid is True, soft_violation_count indicates the number of soft rules broken.
        """
        # ==========================================
        # STAGE 1: HARD CONSTRAINTS
        # ==========================================
        
        # 1. Active employee
        if staff.status != 'Active':
            return False, 0

        # 2. Not on leave
        leaves = context.leaves_by_staff.get(str(staff.id), [])
        for leave in leaves:
            if leave.start_date <= current_day <= leave.end_date:
                return False, 0

        cand_start = datetime.combine(current_day, template.start_time)
        cand_end = cand_start + timedelta(hours=float(template.duration_hours))
        staff_shifts = context.assignments_by_staff.get(str(staff.id), [])

        # 3. No duplicate or overlapping shift
        for shift in staff_shifts:
            s_date = shift.shift_date
            s_start = datetime.combine(s_date, shift.start_time)
            s_end = s_start + timedelta(hours=float(shift.duration_hours))

            # Overlap check
            if cand_start < s_end and s_start < cand_end:
                return False, 0

        # ==========================================
        # STAGE 2: SOFT CONSTRAINTS
        # ==========================================
        soft_violations = 0
        
        # 1. Availability / Preferred days off
        day_name = current_day.strftime('%a')
        avail = context.availability_by_staff.get(str(staff.id))
        if avail and avail.available_days:
            if day_name not in avail.available_days:
                soft_violations += 1

        rest_hours = float(context.rules.minimum_rest_hours)
        cand_dur = float(template.duration_hours)

        daily_hours = 0.0
        weekly_hours = 0.0
        monthly_hours = 0.0
        night_count_week = 0
        night_count_month = 0
        
        monday = current_day - timedelta(days=current_day.weekday())
        sunday = monday + timedelta(days=6)
        
        month_start = current_day.replace(day=1)
        next_month = month_start.replace(day=28) + timedelta(days=4)
        month_end = next_month - timedelta(days=next_month.day)

        work_dates = set()

        for shift in staff_shifts:
            s_date = shift.shift_date
            s_start = datetime.combine(s_date, shift.start_time)
            s_end = s_start + timedelta(hours=float(shift.duration_hours))
            s_dur = float(shift.duration_hours)

            if s_date == current_day:
                daily_hours += s_dur
                
            # 2. Rest Period
            if s_end <= cand_start:
                rest_diff = (cand_start - s_end).total_seconds() / 3600.0
                if rest_diff < rest_hours:
                    soft_violations += 1
            elif cand_end <= s_start:
                rest_diff = (s_start - cand_end).total_seconds() / 3600.0
                if rest_diff < rest_hours:
                    soft_violations += 1

            if monday <= s_date <= sunday:
                weekly_hours += s_dur
                if shift.shift and shift.shift.shift_type == 'night':
                    night_count_week += 1
                    
            if month_start <= s_date <= month_end:
                monthly_hours += s_dur
                if shift.shift and shift.shift.shift_type == 'night':
                    night_count_month += 1
                    
            work_dates.add(s_date)

        # 3. Maximum Hours (Daily/Weekly/Monthly)
        if daily_hours + cand_dur > float(context.rules.max_hours_per_day):
            soft_violations += 1

        if weekly_hours + cand_dur > float(context.rules.max_hours_per_week):
            soft_violations += 1

        if monthly_hours + cand_dur > float(context.rules.max_hours_per_month):
            soft_violations += 1

        # 4. Maximum Consecutive Days
        work_dates.add(current_day)
        run_len = 1
        check_date = current_day - timedelta(days=1)
        while check_date in work_dates:
            run_len += 1
            check_date -= timedelta(days=1)
        check_date = current_day + timedelta(days=1)
        while check_date in work_dates:
            run_len += 1
            check_date += timedelta(days=1)
            
        if run_len > context.rules.max_consecutive_days:
            soft_violations += 1

        # 5. Night Shift Limits
        if template.shift_type == 'night':
            if night_count_week + 1 > context.rules.max_night_per_week:
                soft_violations += 1
            if night_count_month + 1 > context.rules.max_night_per_month:
                soft_violations += 1

        return True, soft_violations
