"""Which aircraft CalDART's insurance policy covers, judged from the coverage policy.

An account administrator records, in the one ``AircraftCoveragePolicy`` row, the
aircraft categories and airworthiness classifications the policy excludes.
:func:`current_rule` reads that row once, with the organization's name, and
:meth:`CoverageRule.judge` answers for one aircraft: excluded, with the reason a DART
leader reads on the aircraft check, or not.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.aircraft.models import AircraftCategory, AircraftCoveragePolicy, Airworthiness
from caldart.org import org_details

#: What an aircraft with no category recorded is answered with.  It is not excluded:
#: nobody can tell, so the check says so rather than guess.
CATEGORY_NOT_RECORDED = "Category not recorded"

#: Each category as the reason names it, in the plural.
CATEGORY_PLURALS: dict[str, str] = {
    AircraftCategory.AIRPLANE: "airplanes",
    AircraftCategory.HELICOPTER: "helicopters",
    AircraftCategory.GYROPLANE: "gyroplanes",
    AircraftCategory.GLIDER: "gliders",
    AircraftCategory.BALLOON: "balloons",
    AircraftCategory.AIRSHIP: "airships",
    AircraftCategory.POWERED_LIFT: "powered-lift aircraft",
    AircraftCategory.WEIGHT_SHIFT: "weight-shift-control aircraft",
    AircraftCategory.POWERED_PARACHUTE: "powered parachutes",
    AircraftCategory.OTHER: "aircraft of other categories",
}

#: Each airworthiness classification as the reason names it, in the plural.
AIRWORTHINESS_PLURALS: dict[str, str] = {
    Airworthiness.STANDARD: "standard-category aircraft",
    Airworthiness.LIMITED: "limited-category aircraft",
    Airworthiness.RESTRICTED: "restricted-category aircraft",
    Airworthiness.EXPERIMENTAL: "experimental aircraft",
    Airworthiness.PROVISIONAL: "provisionally certificated aircraft",
    Airworthiness.MULTIPLE: "aircraft with multiple airworthiness certificates",
    Airworthiness.PRIMARY: "primary-category aircraft",
    Airworthiness.SPECIAL_FLIGHT_PERMIT: "aircraft on a special flight permit",
    Airworthiness.LIGHT_SPORT: "light-sport aircraft",
}


@dataclass(frozen=True)
class Coverage:
    """One aircraft's answer: whether the policy excludes it, and what to say.

    ``reason`` is ``Not covered: <what> are excluded by <organization>'s policy`` for
    an excluded aircraft, :data:`CATEGORY_NOT_RECORDED` for one with no category that
    is not excluded, and blank otherwise.
    """

    excluded: bool
    reason: str


@dataclass(frozen=True)
class CoverageRule:
    """The policy's exclusions and the organization's name, read once and reused."""

    excluded_categories: frozenset[str]
    excluded_airworthiness: frozenset[str]
    organization: str

    def judge(self, *, category: str, airworthiness: str) -> Coverage:
        """The coverage of an aircraft with ``category`` and ``airworthiness``.

        Either one listed by the policy excludes the aircraft; when both are, the reason
        names the category.  A blank value is never listed, so an aircraft with nothing
        recorded is never excluded, and one with no category is answered with
        :data:`CATEGORY_NOT_RECORDED` unless its airworthiness excludes it.
        """
        if category in self.excluded_categories:
            return self._excluded(CATEGORY_PLURALS[category])
        if airworthiness in self.excluded_airworthiness:
            return self._excluded(AIRWORTHINESS_PLURALS[airworthiness])
        if category == "":
            return Coverage(excluded=False, reason=CATEGORY_NOT_RECORDED)
        return Coverage(excluded=False, reason="")

    def _excluded(self, what: str) -> Coverage:
        """An exclusion of ``what``, worded as the aircraft check prints it."""
        return Coverage(
            excluded=True,
            reason=f"Not covered: {what} are excluded by {self.organization}'s policy",
        )


def rule_for(policy: AircraftCoveragePolicy) -> CoverageRule:
    """The rule ``policy`` states, naming the organization from the site settings.

    A policy that excludes nothing never names the organization, so the site settings
    are read only when an exclusion could need them.
    """
    excludes_any = len(policy.excluded_categories) + len(policy.excluded_airworthiness) > 0
    return CoverageRule(
        excluded_categories=frozenset(policy.excluded_categories),
        excluded_airworthiness=frozenset(policy.excluded_airworthiness),
        organization=org_details().name if excludes_any else "",
    )


def current_rule() -> CoverageRule:
    """The rule the stored policy states now (an empty policy when none is stored)."""
    return rule_for(AircraftCoveragePolicy.load())
