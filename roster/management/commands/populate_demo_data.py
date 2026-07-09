import uuid
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from roster.models import (
    StaffProfile, ShiftTemplate, RosterRule, Availability, 
    LeaveRequest, ClinicalRole, ShiftType
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Populates the database with default demo data for the MedRoster system.'

    def handle(self, *args, **options):
        self.stdout.write("Populating demo data...")

        # 1. Create default manager
        manager_email = "manager@medroster.health"
        manager, created = User.objects.get_or_create(
            email=manager_email,
            defaults={
                'username': manager_email,
                'full_name': 'Dr. Sarah Jenkins',
                'role': 'manager',
                'employee_id': 'MGR-001',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            manager.set_password('medroster123')
            manager.save()
            self.stdout.write(f"Created manager user: {manager_email} (password: medroster123)")

        # 2. Create shift templates
        self._create_shift_templates()

        # 3. Create default roster rules
        rules, created = RosterRule.objects.get_or_create(
            id=1,
            defaults={
                'max_hours_per_day': 12.0,
                'max_hours_per_week': 48.0,
                'max_hours_per_month': 176.0,
                'max_consecutive_days': 5,
                'minimum_rest_hours': 11.0,
                'max_night_per_week': 3,
                'max_night_per_month': 10,
                'equal_shift_distribution': True,
                'equal_weekend_distribution': True,
                'equal_night_distribution': True,
                'balance_workload': True
            }
        )
        if created:
            self.stdout.write("Created default roster rules.")

        # 4. Create clinical staff
        # 5 Doctors
        doctors_data = [
            ("Aarav Patel", "aarav.patel@medroster.health", "DOC-001", "#ef4444"),
            ("Priya Sharma", "priya.sharma@medroster.health", "DOC-002", "#f97316"),
            ("Liam Brown", "liam.brown@medroster.health", "DOC-003", "#f59e0b"),
            ("Sophia Garcia", "sophia.garcia@medroster.health", "DOC-004", "#10b981"),
            ("Michael Jones", "michael.jones@medroster.health", "DOC-005", "#06b6d4"),
        ]
        
        # 5 Nurses
        nurses_data = [
            ("Emily Martin", "emily.martin@medroster.health", "NRS-001", "#3b82f6"),
            ("Daniel Jackson", "daniel.jackson@medroster.health", "NRS-002", "#6366f1"),
            ("Abigail Moore", "abigail.moore@medroster.health", "NRS-003", "#8b5cf6"),
            ("Matthew Lee", "matthew.lee@medroster.health", "NRS-004", "#ec4899"),
            ("Elizabeth Perez", "elizabeth.perez@medroster.health", "NRS-005", "#f43f5e"),
        ]

        # 5 Support Staff
        support_data = [
            ("David Miller", "david.miller@medroster.health", "SPT-001", "#14b8a6"),
            ("Isabella Davis", "isabella.davis@medroster.health", "SPT-002", "#84cc16"),
            ("Grace Robinson", "grace.robinson@medroster.health", "SPT-003", "#eab308"),
            ("Donald Clark", "donald.clark@medroster.health", "SPT-004", "#64748b"),
            ("Ella Sanchez", "ella.sanchez@medroster.health", "SPT-005", "#a855f7"),
        ]

        staff_profiles = []
        
        # Helper to create staff users & profiles
        def create_staff_entries(data_list, role):
            for name, email, emp_id, color in data_list:
                user, u_created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'username': email,
                        'full_name': name,
                        'role': 'staff',
                        'employee_id': emp_id,
                        'phone': '555-010' + emp_id[-1]
                    }
                )
                if u_created:
                    user.set_password('medroster123')
                    user.save()
                
                # Fetch StaffProfile (automatically created by post_save signal) and update clinical fields
                profile = user.staff_profile
                profile.role = role
                profile.department = "Emergency Department" if role == ClinicalRole.DOCTOR else "General Ward"
                profile.avatar_color = color
                profile.employment_type = "Full-time"
                profile.status = "Active"
                profile.save()
                
                staff_profiles.append(profile)
                self.stdout.write(f"Created staff profile for: {name} ({role})")

        create_staff_entries(doctors_data, ClinicalRole.DOCTOR)
        create_staff_entries(nurses_data, ClinicalRole.NURSE)
        create_staff_entries(support_data, ClinicalRole.SUPPORT_STAFF)

        # 5. Populate default availability and leaves for demo staff
        self._populate_availabilities_and_leaves(staff_profiles)

        self.stdout.write(self.style.SUCCESS("Successfully populated all default demo data!"))

    def _create_shift_templates(self):
        templates_data = [
            ("Morning Shift", "07:00:00", "15:00:00", 8.0, ShiftType.MORNING, "#3B82F6"),
            ("Evening Shift", "15:00:00", "23:00:00", 8.0, ShiftType.EVENING, "#8B5CF6"),
            ("Night Shift", "23:00:00", "07:00:00", 8.0, ShiftType.NIGHT, "#1E293B"),
        ]
        for name, start, end, dur, s_type, color in templates_data:
            ShiftTemplate.objects.get_or_create(
                shift_type=s_type,
                defaults={
                    'name': name,
                    'start_time': start,
                    'end_time': end,
                    'duration_hours': dur,
                    'color': color
                }
            )
            self.stdout.write(f"Ensured shift template: {name}")

    def _populate_availabilities_and_leaves(self, staff_profiles):
        today = date.today()
        
        # Populate availability defaults
        for idx, staff in enumerate(staff_profiles):
            # Alternate preference days off for demo variance
            pref_days_off = ["Sat", "Sun"] if idx % 2 == 0 else ["Wed", "Thu"]
            pref_shift = ShiftType.MORNING if idx % 3 == 0 else ShiftType.EVENING if idx % 3 == 1 else ShiftType.NIGHT
            
            Availability.objects.create(
                staff=staff,
                available_days=["Mon", "Tue", "Wed", "Thu", "Fri"] if idx % 2 == 0 else ["Mon", "Tue", "Fri", "Sat", "Sun"],
                preferred_shift=pref_shift,
                preferred_days_off=pref_days_off,
                notes="Prefer early/mid day shifts if possible."
            )

        # Populate a few sample leaves for testing roster generator overlaps
        if len(staff_profiles) > 2:
            # Leave for staff 1: starts next week
            LeaveRequest.objects.create(
                staff=staff_profiles[0],
                leave_type='Vacation',
                start_date=today + timedelta(days=2),
                end_date=today + timedelta(days=5),
                reason="Family trip",
                status='Approved'
            )
            # Leave for staff 2: starts today
            LeaveRequest.objects.create(
                staff=staff_profiles[1],
                leave_type='Sick',
                start_date=today,
                end_date=today + timedelta(days=1),
                reason="Medical emergency",
                status='Approved'
            )
            # Leave for staff 3: pending approval
            LeaveRequest.objects.create(
                staff=staff_profiles[2],
                leave_type='Casual',
                start_date=today + timedelta(days=10),
                end_date=today + timedelta(days=12),
                reason="Personal work",
                status='Pending'
            )
            self.stdout.write("Created demo leave requests and availabilities.")
