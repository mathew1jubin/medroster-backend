from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ShiftTemplateViewSet, RosterRuleViewSet, AvailabilityViewSet,
    LeaveRequestViewSet, RosterViewSet, RosterAssignmentViewSet,
    SwapRequestViewSet, ConflictViewSet, NotificationViewSet,
    ActivityLogViewSet
)

router = DefaultRouter()
router.register(r'templates', ShiftTemplateViewSet, basename='shifttemplate')
router.register(r'rules', RosterRuleViewSet, basename='rosterrules')
router.register(r'availability', AvailabilityViewSet, basename='availability')
router.register(r'leave-requests', LeaveRequestViewSet, basename='leaverequest')
router.register(r'rosters', RosterViewSet, basename='roster')
router.register(r'shifts', RosterAssignmentViewSet, basename='rostershift')
router.register(r'swap-requests', SwapRequestViewSet, basename='shiftswaprequest')
router.register(r'conflicts', ConflictViewSet, basename='conflict')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'activity-logs', ActivityLogViewSet, basename='activitylog')

urlpatterns = [
    path('', include(router.urls)),
]

