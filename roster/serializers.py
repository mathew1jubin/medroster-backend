from rest_framework import serializers
from .models import (
    ShiftTemplate, RosterRule, Availability, LeaveRequest, 
    Roster, RosterAssignment, SwapRequest, Conflict, Notification, StaffProfile, ActivityLog
)

class ShiftTemplateSerializer(serializers.ModelSerializer):
    start = serializers.TimeField(source='start_time')
    end = serializers.TimeField(source='end_time')
    type = serializers.CharField(source='shift_type')

    class Meta:
        model = ShiftTemplate
        fields = ['id', 'name', 'start', 'end', 'type', 'color']


class RosterRulesSerializer(serializers.ModelSerializer):
    maxHoursPerDay = serializers.DecimalField(source='max_hours_per_day', max_digits=4, decimal_places=2)
    maxHoursPerWeek = serializers.DecimalField(source='max_hours_per_week', max_digits=5, decimal_places=2)
    maxHoursPerMonth = serializers.DecimalField(source='max_hours_per_month', max_digits=6, decimal_places=2)
    maxConsecutiveDays = serializers.IntegerField(source='max_consecutive_days')
    minRestHours = serializers.DecimalField(source='minimum_rest_hours', max_digits=4, decimal_places=2)
    maxNightsPerWeek = serializers.IntegerField(source='max_night_per_week')
    maxNightsPerMonth = serializers.IntegerField(source='max_night_per_month')
    equalShiftDistribution = serializers.BooleanField(source='equal_shift_distribution')
    equalWeekendDistribution = serializers.BooleanField(source='equal_weekend_distribution')
    equalNightDistribution = serializers.BooleanField(source='equal_night_distribution')
    balanceWorkload = serializers.BooleanField(source='balance_workload')

    class Meta:
        model = RosterRule
        fields = [
            'id', 'maxHoursPerDay', 'maxHoursPerWeek', 'maxHoursPerMonth', 
            'maxConsecutiveDays', 'minRestHours', 'maxNightsPerWeek', 
            'maxNightsPerMonth', 'equalShiftDistribution', 'equalWeekendDistribution', 
            'equalNightDistribution', 'balanceWorkload'
        ]


class AvailabilitySerializer(serializers.ModelSerializer):
    staffId = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    availableDays = serializers.JSONField(source='available_days')
    preferredShift = serializers.CharField(source='preferred_shift', required=False, allow_null=True)
    preferredDaysOff = serializers.JSONField(source='preferred_days_off')

    class Meta:
        model = Availability
        fields = ['id', 'staffId', 'availableDays', 'preferredShift', 'preferredDaysOff', 'notes']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['staffId'] = instance.staff.user_id if instance.staff else None
        return rep

    def create(self, validated_data):
        staff_id = validated_data.pop('staffId', None)
        if staff_id:
            validated_data['staff'] = StaffProfile.objects.get(user_id=staff_id)
        return super().create(validated_data)


class LeaveRequestSerializer(serializers.ModelSerializer):
    staffId = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    type = serializers.CharField(source='leave_type')
    startDate = serializers.DateField(source='start_date')
    endDate = serializers.DateField(source='end_date')
    totalDays = serializers.ReadOnlyField(source='total_days')
    submittedOn = serializers.DateField(source='submitted_on', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = ['id', 'staffId', 'type', 'startDate', 'endDate', 'totalDays', 'reason', 'status', 'submittedOn']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['staffId'] = instance.staff.user_id if instance.staff else None
        return rep

    def create(self, validated_data):
        staff_id = validated_data.pop('staffId', None)
        if not staff_id:
            request = self.context.get('request')
            if request and request.user and hasattr(request.user, 'staff_profile'):
                validated_data['staff'] = request.user.staff_profile
            else:
                raise serializers.ValidationError({"staffId": "Could not infer staff profile from user session."})
        else:
            validated_data['staff'] = StaffProfile.objects.get(user_id=staff_id)
        return super().create(validated_data)


class RosterSerializer(serializers.ModelSerializer):
    startDate = serializers.DateField(source='start_date')
    endDate = serializers.DateField(source='end_date')

    class Meta:
        model = Roster
        fields = ['id', 'name', 'startDate', 'endDate', 'status']


class RosterShiftSerializer(serializers.ModelSerializer):
    """
    RosterAssignmentSerializer mapped back to RosterShift name for backward compatibility.
    """
    date = serializers.DateField(source='shift_date')
    staffId = serializers.UUIDField(write_only=True)
    rosterId = serializers.UUIDField(write_only=True)
    
    shift = serializers.SerializerMethodField()

    class Meta:
        model = RosterAssignment
        fields = ['id', 'rosterId', 'staffId', 'date', 'shift', 'start_time', 'end_time', 'duration_hours', 'notes', 'status']

    def get_shift(self, obj):
        if obj.shift:
            return obj.shift.shift_type
        # Fallback based on start time
        hour = obj.start_time.hour
        if 5 <= hour < 13:
            return 'morning'
        elif 13 <= hour < 21:
            return 'evening'
        else:
            return 'night'

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['rosterId'] = instance.roster_id
        rep['staffId'] = instance.staff.user_id if instance.staff else None
        return rep

    def create(self, validated_data):
        roster_id = validated_data.pop('rosterId')
        staff_id = validated_data.pop('staffId')
        
        validated_data['roster'] = Roster.objects.get(id=roster_id)
        validated_data['staff'] = StaffProfile.objects.get(user_id=staff_id)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'rosterId' in validated_data:
            roster_id = validated_data.pop('rosterId')
            instance.roster = Roster.objects.get(id=roster_id)
        if 'staffId' in validated_data:
            staff_id = validated_data.pop('staffId')
            instance.staff = StaffProfile.objects.get(user_id=staff_id)
        return super().update(instance, validated_data)


class ShiftSwapRequestSerializer(serializers.ModelSerializer):
    """
    SwapRequestSerializer mapped to ShiftSwapRequest name for backward compatibility.
    """
    staffId = serializers.UUIDField(write_only=True)
    requestedStaffId = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    requesterShiftId = serializers.UUIDField(write_only=True)
    offeredShiftId = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    managerNotes = serializers.CharField(source='manager_notes', required=False, allow_null=True, allow_blank=True)
    
    currentShift = serializers.SerializerMethodField(read_only=True)
    requestedShift = serializers.SerializerMethodField(read_only=True)
    date = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SwapRequest
        fields = [
            'id', 'staffId', 'requestedStaffId', 'requesterShiftId', 'offeredShiftId', 
            'currentShift', 'requestedShift', 'date', 'reason', 'status', 'managerNotes'
        ]

    def get_currentShift(self, obj):
        if obj.current_shift and obj.current_shift.shift:
            return obj.current_shift.shift.shift_type
        return 'night'

    def get_requestedShift(self, obj):
        if obj.requested_shift and obj.requested_shift.shift:
            return obj.requested_shift.shift.shift_type
        return 'morning'

    def get_date(self, obj):
        if obj.current_shift:
            return obj.current_shift.shift_date.strftime('%Y-%m-%d')
        return ''

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['staffId'] = instance.requester.user_id if instance.requester else None
        rep['requestedStaffId'] = instance.requested_staff.user_id if instance.requested_staff else None
        rep['requesterShiftId'] = instance.current_shift_id
        rep['offeredShiftId'] = instance.requested_shift_id if instance.requested_shift else None
        return rep

    def create(self, validated_data):
        staff_id = validated_data.pop('staffId')
        requested_staff_id = validated_data.pop('requestedStaffId', None)
        requester_shift_id = validated_data.pop('requesterShiftId')
        offered_shift_id = validated_data.pop('offeredShiftId', None)

        validated_data['requester'] = StaffProfile.objects.get(user_id=staff_id)
        if requested_staff_id:
            validated_data['requested_staff'] = StaffProfile.objects.get(user_id=requested_staff_id)
        validated_data['current_shift'] = RosterAssignment.objects.get(id=requester_shift_id)
        if offered_shift_id:
            validated_data['requested_shift'] = RosterAssignment.objects.get(id=offered_shift_id)

        return super().create(validated_data)


class ConflictSerializer(serializers.ModelSerializer):
    rosterId = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    staffId = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    type = serializers.CharField(source='conflict_type')
    expectedValue = serializers.CharField(source='expected_value', required=False, allow_null=True, allow_blank=True)
    actualValue = serializers.CharField(source='actual_value', required=False, allow_null=True, allow_blank=True)
    suggestedResolution = serializers.CharField(source='suggested_resolution', required=False)
    planningBoardRedirect = serializers.CharField(source='planning_board_redirect', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    resolvedAt = serializers.DateTimeField(source='resolved_at', read_only=True)
    resolvedBy = serializers.SerializerMethodField(read_only=True)
    ignoredBy = serializers.SerializerMethodField(read_only=True)
    ignoredAt = serializers.DateTimeField(source='ignored_at', read_only=True)
    optionalNote = serializers.CharField(source='optional_note', required=False, allow_null=True, allow_blank=True)
    message = serializers.CharField(source='description', read_only=True)

    class Meta:
        model = Conflict
        fields = [
            'id', 'rosterId', 'staffId', 'type', 'message', 'severity', 'date', 'status',
            'title', 'location', 'description', 'reason', 'expectedValue', 'actualValue',
            'suggestedResolution', 'planningBoardRedirect', 'ignored', 'resolved',
            'createdAt', 'updatedAt', 'resolvedAt', 'resolvedBy', 'ignoredBy', 'ignoredAt', 'optionalNote',
            'shift'
        ]

    def get_resolvedBy(self, obj):
        return obj.resolved_by.full_name or obj.resolved_by.email if obj.resolved_by else None

    def get_ignoredBy(self, obj):
        return obj.ignored_by.full_name or obj.ignored_by.email if obj.ignored_by else None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['rosterId'] = instance.roster_id
        rep['staffId'] = instance.employee.user_id if instance.employee else None
        rep['shift'] = instance.shift.shift_type if instance.shift else None
        return rep

    def create(self, validated_data):
        roster_id = validated_data.pop('rosterId', None)
        staff_id = validated_data.pop('staffId', None)
        if roster_id:
            validated_data['roster'] = Roster.objects.get(id=roster_id)
        if staff_id:
            validated_data['employee'] = StaffProfile.objects.get(user_id=staff_id)
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id')
    read = serializers.BooleanField(source='is_read')
    timestamp = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'userId', 'type', 'title', 'message', 'read', 'action_url', 'metadata', 'timestamp']


class ActivityLogSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = ActivityLog
        fields = ['id', 'timestamp', 'action', 'message', 'user']

