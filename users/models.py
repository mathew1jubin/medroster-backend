import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class UserRole(models.TextChoices):
    MANAGER = 'manager', 'Manager'
    STAFF = 'staff', 'Staff'

class User(AbstractUser):
    """
    Custom User model extending AbstractUser.
    Maps to the 'profiles' table in the database for backwards compatibility.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.TextField()
    email = models.EmailField(unique=True)
    
    # Custom fields requested by user
    employee_id = models.TextField(unique=True, null=True, blank=True)
    phone = models.TextField(null=True, blank=True)
    role = models.CharField(
        max_length=10, 
        choices=UserRole.choices, 
        default=UserRole.STAFF
    )
    
    # Trackers
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Set up username to use email
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)

    class Meta:
        db_table = 'profiles'
        indexes = [
            models.Index(fields=['role'], name='idx_profiles_role'),
        ]

    def __str__(self):
        return f"{self.full_name or self.email} ({self.role})"

