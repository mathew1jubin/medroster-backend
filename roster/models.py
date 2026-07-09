import uuid
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

# ============================================================
# ENUMS / CHOICES
# ============================================================

class ShiftType(models.TextChoices):
    MORNING = 'morning', 'Morning'
    EVENING = 'evening', 'Evening'
    NIGHT = 'night', 'Night'
    CUSTOM = 'custom', 'Custom'

class ClinicalRole(models.TextChoices):
    DOCTOR = 'Doctor', 'Doctor'
    NURSE = 'Nurse', 'Nurse'
    SUPPORT_STAFF = 'Support Staff', 'Support Staff'

class LeaveType(models.TextChoices):
    SICK = 'Sick', 'Sick'
    CASUAL = 'Casual', 'Casual'
    VACATION = 'Vacation', 'Vacation'
    EMERGENCY = 'Emergency', 'Emergency'
    MATERNITY = 'Maternity', 'Maternity'

class LeaveStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    APPROVED = 'Approved', 'Approved'
    REJECTED = 'Rejected', 'Rejected'
    CANCELLED = 'Cancelled', 'Cancelled'

class SwapStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    ACCEPTED = 'Accepted', 'Accepted'
    REJECTED = 'Rejected', 'Rejected'
    CANCELLED = 'Cancelled', 'Cancelled'
    MANAGER_APPROVED = 'Manager_Approved', 'Manager Approved'
    MANAGER_REJECTED = 'Manager_Rejected', 'Manager Rejected'

class RosterStatus(models.TextChoices):
    DRAFT = 'Draft', 'Draft'
    PUBLISHED = 'Published', 'Published'
    ARCHIVED = 'Archived', 'Archived'

class ShiftStatus(models.TextChoices):
    SCHEDULED = 'Scheduled', 'Scheduled'
    COMPLETED = 'Completed', 'Completed'
    CANCELLED = 'Cancelled', 'Cancelled'
    SWAPPED = 'Swapped', 'Swapped'

class ConflictType(models.TextChoices):
    DOUBLE_BOOKING = 'DOUBLE_BOOKING', 'Double Booking'
    SHIFT_OVERLAP = 'SHIFT_OVERLAP', 'Shift Overlap'
    LEAVE_VIOLATION = 'LEAVE_VIOLATION', 'Leave Violation'
    AVAILABILITY_VIOLATION = 'AVAILABILITY_VIOLATION', 'Availability Violation'
    REST_RULE_VIOLATION = 'REST_RULE_VIOLATION', 'Rest Rule Violation'
    OVERTIME_LIMIT_EXCEEDED = 'OVERTIME_LIMIT_EXCEEDED', 'Overtime Limit Exceeded'
    UNDERSTAFFED_SHIFT = 'UNDERSTAFFED_SHIFT', 'Understaffed Shift'
    OVERSTAFFED_SHIFT = 'OVERSTAFFED_SHIFT', 'Overstaffed Shift'
    MAX_CONSECUTIVE_DAYS_EXCEEDED = 'MAX_CONSECUTIVE_DAYS_EXCEEDED', 'Max Consecutive Days Exceeded'
    MAX_NIGHT_SHIFT_LIMIT_EXCEEDED = 'MAX_NIGHT_SHIFT_LIMIT_EXCEEDED', 'Max Night Shift Limit Exceeded'

class ConflictSeverity(models.TextChoices):
    CRITICAL = 'Critical', 'Critical'
    HIGH = 'High', 'High'
    MEDIUM = 'Medium', 'Medium'

class ConflictStatus(models.TextChoices):
    OPEN = 'Open', 'Open'
    RESOLVED = 'Resolved', 'Resolved'
    IGNORED = 'Ignored', 'Ignored'

class NotifType(models.TextChoices):
    LEAVE_APPROVED = 'Leave_Approved', 'Leave Approved'
    LEAVE_REJECTED = 'Leave_Rejected', 'Leave Rejected'
    SHIFT_CHANGED = 'Shift_Changed', 'Shift Changed'
    ROSTER_PUBLISHED = 'Roster_Published', 'Roster Published'
    SWAP_APPROVED = 'Swap_Approved', 'Swap Approved'
    SWAP_REJECTED = 'Swap_Rejected', 'Swap Rejected'
    CONFLICT_DETECTED = 'Conflict_Detected', 'Conflict Detected'

# ============================================================
# MODELS
# ============================================================

class StaffProfile(models.Model):
    """
    Stores clinical and department details for a staff member.
    Links 1-to-1 with the custom User model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.CharField(max_length=20, choices=ClinicalRole.choices, default=ClinicalRole.NURSE)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('Active', 'Active'), ('On Leave', 'On Leave'), ('Inactive', 'Inactive')],
        default='Active'
    )
    department = models.TextField(null=True, blank=True)
    employment_type = models.CharField(max_length=20, default='Full-time')
    avatar_color = models.TextField(default='#6366f1')
    joined_on = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'staff_profiles'

    def __str__(self):
        return f"{self.user.full_name or self.email} - {self.role}"


class ShiftTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8.0)
    shift_type = models.CharField(max_length=20, choices=ShiftType.choices, default=ShiftType.MORNING)
    color = models.TextField(default='#3B82F6')

    class Meta:
        db_table = 'shift_templates'

    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"


class RosterRule(models.Model):
    max_hours_per_day = models.DecimalField(max_digits=4, decimal_places=2, default=12)
    max_hours_per_week = models.DecimalField(max_digits=5, decimal_places=2, default=48)
    max_hours_per_month = models.DecimalField(max_digits=6, decimal_places=2, default=176)
    max_consecutive_days = models.IntegerField(default=5)
    minimum_rest_hours = models.DecimalField(max_digits=4, decimal_places=2, default=11)
    max_night_per_week = models.IntegerField(default=3)
    max_night_per_month = models.IntegerField(default=10)
    equal_shift_distribution = models.BooleanField(default=True)
    equal_weekend_distribution = models.BooleanField(default=True)
    equal_night_distribution = models.BooleanField(default=True)
    balance_workload = models.BooleanField(default=True)

    class Meta:
        db_table = 'roster_rules'

    def save(self, *args, **kwargs):
        self.id = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Global Roster Rules"


class Availability(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, db_column='staff_id', related_name='availabilities')
    date = models.DateField(null=True, blank=True)
    availability = models.CharField(max_length=20, default='Available', null=True, blank=True)
    
    # Backwards compatibility fields for frontend JSON structures
    available_days = models.JSONField(default=list)
    preferred_shift = models.CharField(max_length=20, choices=ShiftType.choices, null=True, blank=True)
    preferred_days_off = models.JSONField(default=list)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'availability'
        indexes = [
            models.Index(fields=['staff'], name='idx_avail_staff_id'),
        ]

    def __str__(self):
        return f"Availability for {self.staff.user.full_name or self.staff.email}"


class LeaveRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, db_column='staff_id', related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=LeaveStatus.choices, default=LeaveStatus.PENDING)
    submitted_on = models.DateField(auto_now_add=True)

    @property
    def total_days(self):
        return (self.end_date - self.start_date).days + 1

    class Meta:
        db_table = 'leave_requests'
        indexes = [
            models.Index(fields=['staff'], name='idx_leave_staff_id'),
            models.Index(fields=['status'], name='idx_leave_status'),
            models.Index(fields=['start_date', 'end_date'], name='idx_leave_dates'),
        ]

    def __str__(self):
        return f"{self.staff.user.full_name or self.staff.email} - {self.leave_type} ({self.status})"


class Roster(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=RosterStatus.choices, default=RosterStatus.DRAFT)
    
    # Target Architecture Fields
    date = models.DateField(null=True, blank=True)
    shift = models.CharField(max_length=50, null=True, blank=True)
    staff = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_rosters')
    published = models.BooleanField(default=False)
    requirements = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='published_rosters')

    class Meta:
        db_table = 'rosters'
        indexes = [
            models.Index(fields=['status'], name='idx_rosters_status'),
            models.Index(fields=['start_date', 'end_date'], name='idx_rosters_dates'),
        ]

    def save(self, *args, **kwargs):
        self.published = (self.status == RosterStatus.PUBLISHED)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class RosterAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    roster = models.ForeignKey(Roster, on_delete=models.CASCADE, db_column='roster_id', related_name='shifts')
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, db_column='staff_id', related_name='assigned_shifts')
    
    # Target Architecture Fields (matching 'shift')
    shift = models.ForeignKey(ShiftTemplate, on_delete=models.SET_NULL, null=True, blank=True, db_column='shift_template_id', related_name='instances')
    
    # Compatibility Fields
    shift_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_hours = models.DecimalField(max_digits=4, decimal_places=2)
    notes = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ShiftStatus.choices, default=ShiftStatus.SCHEDULED)

    class Meta:
        db_table = 'roster_shifts'
        unique_together = ('staff', 'shift_date', 'start_time')
        indexes = [
            models.Index(fields=['roster'], name='idx_r_shifts_roster'),
            models.Index(fields=['staff'], name='idx_r_shifts_staff'),
            models.Index(fields=['shift_date'], name='idx_r_shifts_date'),
        ]

    def __str__(self):
        return f"{self.staff.user.full_name or self.staff.email} - {self.shift_date} {self.start_time}"


class SwapRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, db_column='requester_id', related_name='sent_swaps')
    requested_staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, db_column='requested_staff_id', related_name='received_swaps', null=True, blank=True)
    
    # Target Architecture fields
    current_shift = models.ForeignKey(RosterAssignment, on_delete=models.CASCADE, db_column='requester_shift_id', related_name='swap_requests_as_primary')
    requested_shift = models.ForeignKey(RosterAssignment, on_delete=models.SET_NULL, null=True, blank=True, db_column='offered_shift_id', related_name='swap_requests_as_offer')
    
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=SwapStatus.choices, default=SwapStatus.PENDING)
    manager_notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'shift_swap_requests'
        indexes = [
            models.Index(fields=['requester'], name='idx_swaps_requester'),
            models.Index(fields=['status'], name='idx_swaps_status'),
        ]

    def __str__(self):
        return f"Swap request from {self.requester.user.full_name or self.requester.email}"


class Conflict(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    roster = models.ForeignKey(Roster, on_delete=models.CASCADE, null=True, blank=True, db_column='roster_id', related_name='conflicts')
    employee = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, null=True, blank=True, db_column='staff_id', related_name='conflicts')
    shift = models.ForeignKey(ShiftTemplate, on_delete=models.SET_NULL, null=True, blank=True, db_column='shift_template_id', related_name='conflicts')
    conflict_type = models.CharField(max_length=50, choices=ConflictType.choices)
    severity = models.CharField(max_length=20, choices=ConflictSeverity.choices, default=ConflictSeverity.MEDIUM)
    status = models.CharField(max_length=20, choices=ConflictStatus.choices, default=ConflictStatus.OPEN)
    
    title = models.CharField(max_length=255, default='')
    location = models.CharField(max_length=255, default='')
    description = models.TextField(default='')
    reason = models.TextField(default='')
    expected_value = models.CharField(max_length=255, default='', null=True, blank=True)
    actual_value = models.CharField(max_length=255, default='', null=True, blank=True)
    suggested_resolution = models.TextField(default='')
    planning_board_redirect = models.TextField(default='')
    
    ignored = models.BooleanField(default=False)
    resolved = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_conflicts')
    
    ignored_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='ignored_conflicts')
    ignored_at = models.DateTimeField(null=True, blank=True)
    optional_note = models.TextField(null=True, blank=True)

    date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'conflicts'
        indexes = [
            models.Index(fields=['roster'], name='idx_conflicts_roster'),
            models.Index(fields=['status'], name='idx_conflicts_status'),
        ]

    def save(self, *args, **kwargs):
        self.resolved = (self.status == ConflictStatus.RESOLVED)
        self.ignored = (self.status == ConflictStatus.IGNORED)
        if self.resolved and not self.resolved_at:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.conflict_type} on {self.date}"




class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Linked to auth User model for delivery
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='user_id', related_name='notifications')
    type = models.CharField(max_length=30, choices=NotifType.choices)
    title = models.TextField()
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    action_url = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['user'], name='idx_notif_user'),
            models.Index(fields=['is_read'], name='idx_notif_is_read'),
            models.Index(fields=['created_at'], name='idx_notif_created'),
        ]

    def __str__(self):
        return f"Notification for {self.user.full_name or self.user.email}: {self.title}"


class ActivityLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=100)
    message = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_logs')

    class Meta:
        db_table = 'activity_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} - {self.timestamp}"


# ============================================================
# SIGNALS
# ============================================================

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_staff_profile(sender, instance, created, **kwargs):
    """
    Ensures that every User has a corresponding StaffProfile for scheduling.
    """
    if kwargs.get('raw'):
        return
    staff_profile, created_profile = StaffProfile.objects.get_or_create(
        user=instance,
        defaults={
            'email': instance.email,
            'phone': instance.phone or '',
            'role': ClinicalRole.NURSE,
            'status': 'Active',
            'employment_type': 'Full-time',
            'avatar_color': '#6366f1'
        }
    )
    if not created_profile:
        # Sync email and phone updates from User
        staff_profile.email = instance.email
        if instance.phone:
            staff_profile.phone = instance.phone
        staff_profile.save()


from django.contrib.auth.signals import user_logged_in

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ActivityLog.objects.create(
        action='User_Login',
        message=f"User {user.full_name or user.email} logged in successfully.",
        user=user
    )

