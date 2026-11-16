"""Reusable behaviour shared by several entities (composition over duplication)."""

from enum import StrEnum

from app.core.exceptions import BusinessRuleError


class StateMachineMixin:
    """Guards status changes with an explicit transition table.

    Subclasses declare `_transitions` (dict[state, set[state]]). Every status change goes
    through `_transition_to`, so an invalid change (e.g. re-opening a sold property) is
    impossible whatever the caller (Open/Closed: new entities only declare their table).
    """

    _transitions: dict[StrEnum, set[StrEnum]] = {}

    def can_transition_to(self, new_status: StrEnum) -> bool:
        return new_status in self._transitions.get(self.status, set())

    def _transition_to(self, new_status: StrEnum) -> None:
        if not self.can_transition_to(new_status):
            raise BusinessRuleError(
                f"Transition impossible : {self.status.value} → {new_status.value}."
            )
        self.status = new_status
