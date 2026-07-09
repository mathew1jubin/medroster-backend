from roster.models import Conflict, RosterAssignment
from datetime import date

class SuggestionEngine:
    @staticmethod
    def populate_details(conflict: Conflict, assignment: RosterAssignment = None, other_assignment: RosterAssignment = None, meta: dict = None):
        c_type = conflict.conflict_type
        date_str = conflict.date.strftime('%Y-%m-%d') if conflict.date else ''
        shift_name = conflict.shift.name if conflict.shift else 'Custom Shift'
        shift_type = conflict.shift.shift_type if conflict.shift else 'custom'
        
        emp_name = ''
        if conflict.employee and conflict.employee.user:
            emp_name = conflict.employee.user.full_name or conflict.employee.email
            
        redirect = f"/manager/planning?date={date_str}&shift={shift_type}"
        conflict.planning_board_redirect = redirect
        
        if c_type == 'DOUBLE_BOOKING':
            conflict.title = f"Double Booking - {emp_name}"
            conflict.location = f"{shift_name} on {date_str}"
            conflict.description = f"{emp_name} is assigned to multiple shifts of the same type ({shift_name}) on {date_str}."
            conflict.reason = "Duplicate assignment created during automated generation or manual edit."
            conflict.expected_value = "Max 1 assignment of this type"
            conflict.actual_value = "Multiple assignments"
            conflict.suggested_resolution = f"Remove one of the {shift_name} assignments for {emp_name} on the Planning Board."
            
        elif c_type == 'SHIFT_OVERLAP':
            conflict.title = f"Shift Overlap - {emp_name}"
            conflict.location = f"{shift_name} on {date_str}"
            
            o_name = other_assignment.shift.name if other_assignment and other_assignment.shift else 'Custom'
            conflict.description = f"{emp_name} has overlapping shifts: {shift_name} and {o_name} on {date_str}."
            conflict.reason = "Shift times conflict and create a physical overlap in scheduled hours."
            conflict.expected_value = "Non-overlapping shift schedule"
            conflict.actual_value = "Overlapping hours"
            conflict.suggested_resolution = "Reschedule one of the overlapping shifts using the Planning Board."
            
        elif c_type == 'LEAVE_VIOLATION':
            conflict.title = f"Leave Violation - {emp_name}"
            conflict.location = f"{shift_name} on {date_str}"
            conflict.description = f"{emp_name} is scheduled for a shift on {date_str} while on approved leave."
            conflict.reason = "Approved leave request exists covering this date."
            conflict.expected_value = "Not scheduled (On Leave)"
            conflict.actual_value = "Scheduled"
            conflict.suggested_resolution = f"Reassign the shift to another employee or remove {emp_name} from the shift using the Planning Board."
            
        elif c_type == 'REST_RULE_VIOLATION':
            gap = meta.get('gap', 0.0) if meta else 0.0
            min_rest = meta.get('min_rest', 11.0) if meta else 11.0
            conflict.title = f"Insufficient Rest - {emp_name}"
            conflict.location = f"{shift_name} on {date_str}"
            conflict.description = f"{emp_name} has only {gap:.1f} hours of rest, violating the minimum rest rule of {min_rest:.1f} hours."
            conflict.reason = "Back-to-back shifts scheduled too close to each other."
            conflict.expected_value = f">= {min_rest:.1f} hours rest"
            conflict.actual_value = f"{gap:.1f} hours rest"
            conflict.suggested_resolution = "Reassign one of the shifts to ensure adequate rest period."
            
        elif c_type == 'OVERTIME_LIMIT_EXCEEDED':
            period = meta.get('period', '') if meta else ''
            actual = meta.get('actual', 0.0) if meta else 0.0
            limit = meta.get('limit', 0.0) if meta else 0.0
            conflict.title = f"Overtime Limit Exceeded - {emp_name}"
            conflict.location = f"{shift_name} on {date_str}"
            conflict.description = f"{emp_name} has exceeded the {period} limit of {limit:.1f} hours (scheduled {actual:.1f} hours)."
            conflict.reason = "Scheduling assignments exceed contractual/configured working hour caps."
            conflict.expected_value = f"<= {limit:.1f} hours"
            conflict.actual_value = f"{actual:.1f} hours"
            conflict.suggested_resolution = f"Remove or reassign shifts to bring {emp_name} under the maximum {period} hours threshold."
            
        elif c_type == 'UNDERSTAFFED_SHIFT':
            roles = meta.get('roles', []) if meta else []
            s_name = meta.get('shift_name', '') if meta else ''
            
            if len(roles) == 1:
                role_name = roles[0][0]
                conflict.title = f"Understaffed Shift - {s_name} ({role_name})"
            else:
                conflict.title = f"Understaffed Shift - {s_name}"
                
            conflict.location = f"{s_name} Shift on {date_str}"
            
            role_desc = ", ".join([f"{r} (Req: {req}, Assigned: {act})" for r, req, act in roles])
            conflict.description = f"{s_name} shift is understaffed. Gaps: {role_desc}."
            conflict.reason = "No additional eligible doctor/nurse satisfied scheduling constraints."
            
            expected_desc = ", ".join([f"{r}: {req}" for r, req, act in roles])
            actual_desc = ", ".join([f"{r}: {act}" for r, req, act in roles])
            conflict.expected_value = expected_desc
            conflict.actual_value = actual_desc
            
            missing_desc = ", ".join([f"{r} ×{req - act}" for r, req, act in roles])
            conflict.suggested_resolution = f"Assign missing staff ({missing_desc}) using the Planning Board."
            
        elif c_type == 'OVERSTAFFED_SHIFT':
            roles = meta.get('roles', []) if meta else []
            s_name = meta.get('shift_name', '') if meta else ''
            
            if len(roles) == 1:
                role_name = roles[0][0]
                conflict.title = f"Overstaffed Shift - {s_name} ({role_name})"
            else:
                conflict.title = f"Overstaffed Shift - {s_name}"
                
            conflict.location = f"{s_name} Shift on {date_str}"
            
            role_desc = ", ".join([f"{r} (Req: {req}, Assigned: {act})" for r, req, act in roles])
            conflict.description = f"{s_name} shift has excess staffing. Overages: {role_desc}."
            conflict.reason = "Manual override or duplicate roster assignment."
            
            expected_desc = ", ".join([f"{r}: {req}" for r, req, act in roles])
            actual_desc = ", ".join([f"{r}: {act}" for r, req, act in roles])
            conflict.expected_value = expected_desc
            conflict.actual_value = actual_desc
            
            extra_desc = ", ".join([f"{r} ×{act - req}" for r, req, act in roles])
            conflict.suggested_resolution = f"Remove or reassign surplus staff ({extra_desc}) to other shifts on the Planning Board."
            
        elif c_type == 'MAX_CONSECUTIVE_DAYS_EXCEEDED':
            streak = meta.get('streak', 0) if meta else 0
            limit = meta.get('limit', 5) if meta else 5
            conflict.title = f"Max Consecutive Days Exceeded - {emp_name}"
            conflict.location = f"{shift_name} on {date_str}"
            conflict.description = f"{emp_name} has worked {streak} consecutive days, exceeding the limit of {limit} days."
            conflict.reason = "Consecutive day constraint violated."
            conflict.expected_value = f"<= {limit} days"
            conflict.actual_value = f"{streak} days"
            conflict.suggested_resolution = "Reassign a shift in the streak to provide a rest day."
            
        elif c_type == 'MAX_NIGHT_SHIFT_LIMIT_EXCEEDED':
            period = meta.get('period', '') if meta else ''
            actual = meta.get('actual', 0) if meta else 0
            limit = meta.get('limit', 0) if meta else 0
            conflict.title = f"Max Night Shifts Exceeded - {emp_name}"
            conflict.location = f"{shift_name} on {date_str}"
            conflict.description = f"{emp_name} has scheduled {actual} night shifts {period}, exceeding the limit of {limit}."
            conflict.reason = "Health and safety night shift restriction violated."
            conflict.expected_value = f"<= {limit} shifts"
            conflict.actual_value = f"{actual} shifts"
            conflict.suggested_resolution = "Reassign some night shifts to other eligible employees."
            
        else:
            conflict.title = f"Roster Conflict"
            conflict.description = f"Conflict detected on {date_str}."
            conflict.suggested_resolution = "Audit the shift assignments on the Planning Board."
            
        # Set message for backwards compatibility
        conflict.message = conflict.description
