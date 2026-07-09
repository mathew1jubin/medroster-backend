import csv
from django.http import HttpResponse
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from users.models import User
from .models import (
    ShiftTemplate, RosterRule, Availability, LeaveRequest, 
    Roster, RosterAssignment, SwapRequest, Conflict, Notification, 
    StaffProfile, ShiftType, ActivityLog
)
from .serializers import (
    ShiftTemplateSerializer, RosterRulesSerializer, AvailabilitySerializer,
    LeaveRequestSerializer, RosterSerializer, RosterShiftSerializer,
    ShiftSwapRequestSerializer, ConflictSerializer, NotificationSerializer,
    ActivityLogSerializer
)
from .permissions import IsManager, IsOwnerOrManager
from .services.scheduler import SchedulerService


class ShiftTemplateViewSet(viewsets.ModelViewSet):
    queryset = ShiftTemplate.objects.all()
    serializer_class = ShiftTemplateSerializer
    permission_classes = [IsOwnerOrManager]


class RosterRuleViewSet(viewsets.ModelViewSet):
    queryset = RosterRule.objects.all()
    serializer_class = RosterRulesSerializer
    permission_classes = [IsOwnerOrManager]


class AvailabilityViewSet(viewsets.ModelViewSet):
    queryset = Availability.objects.select_related('staff__user').all()
    serializer_class = AvailabilitySerializer
    permission_classes = [IsOwnerOrManager]

    def get_queryset(self):
        # Allow managers to see all, staff to see their own
        user = self.request.user
        if user.is_authenticated and user.role == 'manager':
            return self.queryset
        return self.queryset.filter(staff__user=user)


class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.select_related('staff__user').all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsOwnerOrManager]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.role == 'manager':
            return self.queryset.all()
        return self.queryset.all().filter(staff__user=user)

    @action(detail=True, methods=['post'], permission_classes=[IsManager])
    def approve(self, request, pk=None):
        leave = self.get_object()
        leave.status = 'Approved'
        leave.save()

        # Log Activity
        ActivityLog.objects.create(
            action='Leave_Approved',
            message=f"Leave request for {leave.staff.user.full_name or leave.staff.email} from {leave.start_date} to {leave.end_date} has been approved.",
            user=request.user
        )

        # Send notification to the employee
        Notification.objects.create(
            user=leave.staff.user,
            type='Leave_Approved',
            title='Leave Request Approved',
            message=f'Your leave request from {leave.start_date} to {leave.end_date} has been approved.',
            is_read=False
        )

        return Response(self.get_serializer(leave).data)

    @action(detail=True, methods=['post'], permission_classes=[IsManager])
    def reject(self, request, pk=None):
        leave = self.get_object()
        leave.status = 'Rejected'
        leave.save()

        # Log Activity
        ActivityLog.objects.create(
            action='Leave_Rejected',
            message=f"Leave request for {leave.staff.user.full_name or leave.staff.email} from {leave.start_date} to {leave.end_date} has been rejected.",
            user=request.user
        )

        # Send notification to the employee
        Notification.objects.create(
            user=leave.staff.user,
            type='Leave_Rejected',
            title='Leave Request Rejected',
            message=f'Your leave request from {leave.start_date} to {leave.end_date} has been rejected.',
            is_read=False
        )

        return Response(self.get_serializer(leave).data)


class RosterViewSet(viewsets.ModelViewSet):
    queryset = Roster.objects.select_related('staff__user').prefetch_related('shifts').all()
    serializer_class = RosterSerializer
    permission_classes = [IsOwnerOrManager]

    @action(detail=False, methods=['post'], url_path='generate', permission_classes=[IsManager])
    def generate_roster(self, request):
        """
        Generates a roster using the roster generator service.
        """
        start_date_str = request.data.get('startDate')
        end_date_str = request.data.get('endDate')
        requirements = request.data.get('requirements', {
            'morning': {'Doctor': 2, 'Nurse': 4, 'Support Staff': 2},
            'evening': {'Doctor': 2, 'Nurse': 3, 'Support Staff': 2},
            'night': {'Doctor': 1, 'Nurse': 2, 'Support Staff': 1},
        })

        if not start_date_str or not end_date_str:
            start_date = timezone.now().date()
            end_date = start_date + timedelta(days=7)
        else:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Delete ANY existing roster for the exact same period to ensure Single Source of Truth
            Roster.objects.filter(
                start_date=start_date,
                end_date=end_date
            ).delete()

            # Delegate generation logic to Service
            service = SchedulerService()
            roster, created_shifts = service.generate(start_date, end_date, requirements)

            # Log Activity
            ActivityLog.objects.create(
                action='Roster_Generated',
                message=f"Roster generated successfully for period {start_date} to {end_date}. Created {len(created_shifts)} assignments.",
                user=request.user
            )

        return Response({
            'roster': RosterSerializer(roster).data,
            'shifts': RosterShiftSerializer(created_shifts, many=True).data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='publish', permission_classes=[IsManager])
    def publish_roster(self, request, pk=None):
        roster = self.get_object()
        
        # Delete any OTHER rosters for the same period that are already Published
        # This will cascade delete their associated RosterAssignment and Conflict objects
        Roster.objects.filter(
            start_date=roster.start_date,
            end_date=roster.end_date,
            status='Published'
        ).exclude(id=roster.id).delete()

        roster.status = 'Published'
        roster.published_at = timezone.now()
        roster.published_by = request.user
        roster.save()

        # Log Activity
        ActivityLog.objects.create(
            action='Schedule_Published',
            message=f"Schedule '{roster.name}' has been published.",
            user=request.user
        )

        # Update all associated shifts status
        RosterAssignment.objects.filter(roster=roster).update(status='Scheduled')

        # Run Conflict Detection ONLY after publishing
        from .services.conflict_engine.engine import ConflictEngineService
        conflict_engine = ConflictEngineService()
        conflict_engine.run(roster)

        # Notify all active staff members
        staff_profiles = StaffProfile.objects.exclude(user__role='manager')
        for staff in staff_profiles:
            Notification.objects.create(
                user=staff.user,
                type='Roster_Published',
                title='Roster Published',
                message=f'The roster "{roster.name}" has been published.',
                is_read=False,
                metadata={'rosterId': str(roster.id)}
            )

        return Response(RosterSerializer(roster).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='export-csv', permission_classes=[IsOwnerOrManager])
    def export_csv(self, request, pk=None):
        roster = self.get_object()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="roster_{roster.id}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'Shift Name', 'Start Time', 'End Time', 'Staff Name', 'Role', 'Status'])
        
        shifts = RosterAssignment.objects.filter(roster=roster).select_related('staff__user', 'shift')
        for s in shifts:
            writer.writerow([
                s.shift_date,
                s.shift.name if s.shift else 'Custom Shift',
                s.start_time,
                s.end_time,
                s.staff.user.full_name if s.staff else '',
                s.staff.role if s.staff else '',
                s.status
            ])
        
        return response



class RosterAssignmentViewSet(viewsets.ModelViewSet):
    queryset = RosterAssignment.objects.select_related('roster', 'staff__user', 'shift').all()
    serializer_class = RosterShiftSerializer
    permission_classes = [IsOwnerOrManager]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return self.queryset.none()

        roster_id = self.request.query_params.get('roster')
        if not roster_id:
            return self.queryset.none()

        qs = self.queryset.filter(roster_id=roster_id)

        if user.role == 'manager':
            return qs
        return qs.filter(staff__user=user)

    def list(self, request, *args, **kwargs):
        roster_id = request.query_params.get('roster')
        if not roster_id:
            return Response(
                {'error': 'roster query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().list(request, *args, **kwargs)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # Support the frontend custom "assign" action format: {"entryId": "...", "pick": "..."}
        entry_id = request.data.get('entryId')
        pick = request.data.get('pick')
        
        if entry_id and pick:
            try:
                assignment = RosterAssignment.objects.get(id=entry_id)
            except RosterAssignment.DoesNotExist:
                return Response({'error': 'Assignment not found'}, status=404)
                
            from .models import ShiftTemplate
            template = ShiftTemplate.objects.filter(shift_type=pick).first()
            if not template:
                return Response({'error': f'Shift template for {pick} not found'}, status=400)
                
            assignment.shift = template
            assignment.start_time = template.start_time
            assignment.end_time = template.end_time
            assignment.save()
            
            self._revalidate_conflicts(assignment)
            return Response(self.get_serializer(assignment).data)
            
        # Support drag-and-drop format: {"staffId": "...", "date": "...", "shift": "...", "rosterId": "..."}
        staff_id = request.data.get('staffId')
        date_str = request.data.get('date')
        shift_type = request.data.get('shift')
        roster_id = request.data.get('rosterId')
        
        if staff_id and date_str and shift_type:
            if not roster_id:
                return Response({'error': 'rosterId is required'}, status=status.HTTP_400_BAD_REQUEST)

            from .models import StaffProfile, ShiftTemplate, Roster
            try:
                roster = Roster.objects.get(id=roster_id)
            except Roster.DoesNotExist:
                return Response({'error': 'Roster not found'}, status=404)

            try:
                staff_member = StaffProfile.objects.get(user_id=staff_id)
            except StaffProfile.DoesNotExist:
                return Response({'error': 'Staff member not found'}, status=404)
                
            template = ShiftTemplate.objects.filter(shift_type=shift_type).first()
            if not template:
                return Response({'error': f'Shift template for {shift_type} not found'}, status=400)
                
            from datetime import datetime
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Invalid date format'}, status=400)
                
            assignment = RosterAssignment.objects.filter(
                roster=roster,
                staff=staff_member,
                shift_date=target_date
            ).first()
            
            if assignment:
                assignment.shift = template
                assignment.start_time = template.start_time
                assignment.end_time = template.end_time
                assignment.save()
            else:
                assignment = RosterAssignment.objects.create(
                    roster=roster,
                    staff=staff_member,
                    shift=template,
                    shift_date=target_date,
                    start_time=template.start_time,
                    end_time=template.end_time,
                    duration_hours=8.0,
                    status='Scheduled' if roster.status == 'Published' else 'Draft'
                )
                
            self._revalidate_conflicts(assignment)
            return Response(self.get_serializer(assignment).data, status=201)
            
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        assignment = serializer.save()
        self._revalidate_conflicts(assignment)

    def perform_update(self, serializer):
        assignment = serializer.save()
        self._revalidate_conflicts(assignment)

    def perform_destroy(self, instance):
        roster = instance.roster
        date_val = instance.shift_date
        shift_type = instance.shift.shift_type if instance.shift else 'custom'
        instance.delete()
        
        from .services.conflict_engine.engine import ConflictEngineService
        engine = ConflictEngineService()
        engine.run_for_shift(roster, date_val, shift_type)

    def _revalidate_conflicts(self, assignment):
        roster = assignment.roster
        date_val = assignment.shift_date
        shift_type = assignment.shift.shift_type if assignment.shift else 'custom'
        
        from .services.conflict_engine.engine import ConflictEngineService
        engine = ConflictEngineService()
        engine.run_for_shift(roster, date_val, shift_type)


class SwapRequestViewSet(viewsets.ModelViewSet):
    queryset = SwapRequest.objects.select_related('requester__user', 'requested_staff__user', 'current_shift__shift', 'requested_shift__shift').all()
    serializer_class = ShiftSwapRequestSerializer
    permission_classes = [IsOwnerOrManager]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.role == 'manager':
            return self.queryset
        return self.queryset.filter(requester__user=user) | self.queryset.filter(requested_staff__user=user)

    @action(detail=True, methods=['post'], permission_classes=[IsManager])
    def approve(self, request, pk=None):
        swap = self.get_object()
        swap.status = 'Manager_Approved'
        swap.manager_notes = request.data.get('managerNotes', '')
        swap.save()

        # Swap assignments
        primary_shift = swap.current_shift
        offer_shift = swap.requested_shift

        if primary_shift and offer_shift:
            # Perform actual swap in the database
            primary_staff = primary_shift.staff
            offer_staff = offer_shift.staff
            
            primary_shift.staff = offer_staff
            offer_shift.staff = primary_staff
            
            primary_shift.save()
            offer_shift.save()

        # Notify both users
        Notification.objects.create(
            user=swap.requester.user,
            type='Swap_Approved',
            title='Swap Request Approved',
            message='Your swap request has been approved by the manager.',
            is_read=False
        )
        if swap.requested_staff:
            Notification.objects.create(
                user=swap.requested_staff.user,
                type='Swap_Approved',
                title='Swap Request Approved',
                message='A swap request you accepted has been approved by the manager.',
                is_read=False
            )

        return Response(self.get_serializer(swap).data)

    @action(detail=True, methods=['post'], permission_classes=[IsManager])
    def reject(self, request, pk=None):
        swap = self.get_object()
        swap.status = 'Manager_Rejected'
        swap.manager_notes = request.data.get('managerNotes', '')
        swap.save()

        # Notify requester
        Notification.objects.create(
            user=swap.requester.user,
            type='Swap_Rejected',
            title='Swap Request Rejected',
            message='Your swap request has been rejected by the manager.',
            is_read=False
        )

        return Response(self.get_serializer(swap).data)


class ConflictViewSet(viewsets.ModelViewSet):
    queryset = Conflict.objects.select_related('roster', 'employee__user').all()
    serializer_class = ConflictSerializer
    permission_classes = [IsOwnerOrManager]

    def get_queryset(self):
        roster_id = self.request.query_params.get('roster')
        if not roster_id:
            return self.queryset.none()
        return self.queryset.filter(roster_id=roster_id)

    def list(self, request, *args, **kwargs):
        roster_id = request.query_params.get('roster')
        if not roster_id:
            return Response(
                {'error': 'roster query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[IsManager])
    def ignore(self, request, pk=None):
        conflict = self.get_object()
        conflict.status = 'Ignored'
        conflict.ignored_by = request.user
        conflict.ignored_at = timezone.now()
        conflict.optional_note = request.data.get('note', '') or request.data.get('optionalNote', '') or request.data.get('optional_note', '')
        conflict.save()
        return Response(self.get_serializer(conflict).data)


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.select_related('user').all()
    serializer_class = NotificationSerializer
    permission_classes = [IsOwnerOrManager]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return self.queryset.filter(user=user)
        return self.queryset.none()

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save()
        return Response(self.get_serializer(notif).data)

    @action(detail=False, methods=['post'], url_path='read-all')
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'status': 'All notifications marked as read'})


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActivityLog.objects.select_related('user').all()
    serializer_class = ActivityLogSerializer
    permission_classes = [IsOwnerOrManager]


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'healthy', 'time': timezone.now()})


