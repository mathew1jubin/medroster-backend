from rest_framework import permissions

class IsManager(permissions.BasePermission):
    """
    Allows access only to Manager users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'manager'


class IsStaff(permissions.BasePermission):
    """
    Allows access only to Staff users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'staff'


class IsOwnerOrManager(permissions.BasePermission):
    """
    Object-level permission: Allows access if the object belongs to the user,
    or if the requesting user is a manager.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
            
        if request.user.role == 'manager':
            return True
            
        # Check if the object relates to the staff user
        # Depending on the model, staff field could point to StaffProfile
        staff_profile = getattr(request.user, 'staff_profile', None)
        if not staff_profile:
            return False

        # Match check
        if hasattr(obj, 'staff'):
            return obj.staff == staff_profile
        elif hasattr(obj, 'requester'):
            return obj.requester == staff_profile
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'id') and obj.__class__.__name__ == 'User':
            return obj == request.user
            
        return False
