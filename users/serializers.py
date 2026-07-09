from rest_framework import serializers
from .models import User
from roster.models import Availability, StaffProfile, ClinicalRole

class ProfileSerializer(serializers.ModelSerializer):
    # CamelCase field mapping for frontend compatibility
    employeeId = serializers.CharField(source='employee_id', required=False, allow_null=True, allow_blank=True)
    name = serializers.CharField(source='full_name')
    
    # StaffProfile linked fields
    role = serializers.CharField(required=False, default='Nurse')  # clinical role (Doctor/Nurse/Support Staff)
    department = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    status = serializers.CharField(required=False, default='Active')
    employmentType = serializers.CharField(required=False, default='Full-time')
    avatarColor = serializers.CharField(required=False, default='#6366f1')
    joinedOn = serializers.DateField(read_only=True)
    
    # Custom fields populated from the Availability model
    availableDays = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    preferredShift = serializers.CharField(required=False, default='morning')
    preferredDaysOff = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    systemRole = serializers.CharField(source='role', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'employeeId', 'name', 'email', 'phone', 'role', 
            'department', 'status', 'joinedOn', 'employmentType', 
            'availableDays', 'preferredShift', 'preferredDaysOff', 
            'avatarColor', 'username', 'systemRole'
        ]
        extra_kwargs = {
            'username': {'required': False, 'allow_null': True, 'allow_blank': True}
        }

    def to_representation(self, instance):
        """
        Merge clinical details from StaffProfile and availability details from Availability.
        """
        representation = super().to_representation(instance)
        
        # Get StaffProfile details
        staff_profile = getattr(instance, 'staff_profile', None)
        if staff_profile:
            representation['role'] = staff_profile.role
            representation['department'] = staff_profile.department
            representation['status'] = staff_profile.status
            representation['employmentType'] = staff_profile.employment_type
            representation['avatarColor'] = staff_profile.avatar_color
            representation['joinedOn'] = staff_profile.joined_on
            
            # Get Availability details
            availability = staff_profile.availabilities.first()
            if availability:
                representation['availableDays'] = availability.available_days
                representation['preferredShift'] = availability.preferred_shift or 'morning'
                representation['preferredDaysOff'] = availability.preferred_days_off
            else:
                # Fallbacks matching frontend defaults
                representation['availableDays'] = ["Mon", "Tue", "Wed", "Thu", "Fri"]
                representation['preferredShift'] = 'morning'
                representation['preferredDaysOff'] = ["Sat", "Sun"]
        else:
            # Fallback values if StaffProfile doesn't exist
            representation['role'] = 'Nurse'
            representation['department'] = ''
            representation['status'] = 'Active'
            representation['employmentType'] = 'Full-time'
            representation['avatarColor'] = '#6366f1'
            representation['joinedOn'] = None
            representation['availableDays'] = ["Mon", "Tue", "Wed", "Thu", "Fri"]
            representation['preferredShift'] = 'morning'
            representation['preferredDaysOff'] = ["Sat", "Sun"]
            
        return representation

    def create(self, validated_data):
        # Create User
        user = super().create(validated_data)
        if not user.username and user.email:
            user.username = user.email
            user.save()

        # Update or create the StaffProfile
        role = self.initial_data.get('role', 'Nurse')
        department = self.initial_data.get('department', '')
        status = self.initial_data.get('status', 'Active')
        employment_type = self.initial_data.get('employmentType', 'Full-time')
        avatar_color = self.initial_data.get('avatarColor', '#6366f1')

        # Since signal automatically creates StaffProfile, fetch it and update fields
        staff_profile = user.staff_profile
        staff_profile.role = role
        staff_profile.department = department
        staff_profile.status = status
        staff_profile.employment_type = employment_type
        staff_profile.avatar_color = avatar_color
        staff_profile.save()

        # Extract availability data from initial_data
        available_days = self.initial_data.get('availableDays', ["Mon", "Tue", "Wed", "Thu", "Fri"])
        preferred_shift = self.initial_data.get('preferredShift', 'morning')
        preferred_days_off = self.initial_data.get('preferredDaysOff', ["Sat", "Sun"])

        # Create corresponding Availability object linked to StaffProfile
        Availability.objects.create(
            staff=staff_profile,
            available_days=available_days,
            preferred_shift=preferred_shift,
            preferred_days_off=preferred_days_off
        )
        return user

    def update(self, instance, validated_data):
        user = super().update(instance, validated_data)

        # Update StaffProfile
        staff_profile = user.staff_profile
        if 'role' in self.initial_data:
            staff_profile.role = self.initial_data['role']
        if 'department' in self.initial_data:
            staff_profile.department = self.initial_data['department']
        if 'status' in self.initial_data:
            staff_profile.status = self.initial_data['status']
        if 'employmentType' in self.initial_data:
            staff_profile.employment_type = self.initial_data['employmentType']
        if 'avatarColor' in self.initial_data:
            staff_profile.avatar_color = self.initial_data['avatarColor']
        staff_profile.save()

        # Extract availability details if provided
        has_availability_data = any(k in self.initial_data for k in ['availableDays', 'preferredShift', 'preferredDaysOff'])
        
        if has_availability_data:
            availability, created = Availability.objects.get_or_create(staff=staff_profile)
            if 'availableDays' in self.initial_data:
                availability.available_days = self.initial_data['availableDays']
            if 'preferredShift' in self.initial_data:
                availability.preferred_shift = self.initial_data['preferredShift']
            if 'preferredDaysOff' in self.initial_data:
                availability.preferred_days_off = self.initial_data['preferredDaysOff']
            availability.save()

        return user

