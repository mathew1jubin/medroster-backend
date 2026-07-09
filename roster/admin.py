from django.contrib import admin
from .models import (
    StaffProfile, ShiftTemplate, RosterRule, Availability, LeaveRequest, 
    Roster, RosterAssignment, SwapRequest, Conflict, Notification
)

admin.site.register(StaffProfile)
admin.site.register(ShiftTemplate)
admin.site.register(RosterRule)
admin.site.register(Availability)
admin.site.register(LeaveRequest)
admin.site.register(Roster)
admin.site.register(RosterAssignment)
admin.site.register(SwapRequest)
admin.site.register(Conflict)
admin.site.register(Notification)

