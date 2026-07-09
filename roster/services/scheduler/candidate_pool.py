from typing import List
from ...models import StaffProfile, ClinicalRole

class CandidatePool:
    def __init__(self, staff_profiles: List[StaffProfile]):
        self.staff_profiles = staff_profiles

    def get_candidates(self, role_name: str) -> List[StaffProfile]:
        db_role = self._normalize_role_name(role_name)
        return [s for s in self.staff_profiles if s.role == db_role and s.status == 'Active']

    def _normalize_role_name(self, role_name: str) -> str:
        if role_name in ['Doctors', 'Doctor']:
            return ClinicalRole.DOCTOR
        elif role_name in ['Nurses', 'Nurse']:
            return ClinicalRole.NURSE
        elif role_name in ['Staff', 'Support Staff']:
            return ClinicalRole.SUPPORT_STAFF
        return ClinicalRole.NURSE
