from roster.models import Roster, RosterAssignment, Conflict, RosterRule
from typing import List

class BaseAssignmentValidator:
    def validate(self, roster: Roster, assignment: RosterAssignment, other_assignments: List[RosterAssignment], rules: RosterRule) -> List[Conflict]:
        raise NotImplementedError
