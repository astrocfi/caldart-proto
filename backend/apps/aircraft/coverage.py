"""Which aircraft CalDART's insurance policy covers, judged from the coverage policy.

A system administrator records, in the one ``AircraftCoveragePolicy`` row, the
aircraft categories and airworthiness classifications the policy excludes, and the
least liability an aircraft's own policy must carry.  :func:`current_rule` reads that
row once, with the organization's name, and :meth:`CoverageRule.judge` answers for one
aircraft: excluded, with the reason a DART leader reads on the aircraft check, or not.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.aircraft.models import Aircraft, AircraftCategory, AircraftCoveragePolicy, Airworthiness
from caldart.org import org_details

#: What an aircraft without a recorded category is answered with.  It is not excluded:
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
    an aircraft excluded by its category or airworthiness, ``Not covered: liability is
    under <organization>'s minimum of <amounts>`` for one whose own policy carries too
    little, :data:`CATEGORY_NOT_RECORDED` for one without a category that is not
    excluded, and blank otherwise.
    """

    excluded: bool
    reason: str


def dollars(cents: int) -> str:
    """Whole dollars as a reason prints them, e.g. ``100_000_000`` -> ``$1,000,000``."""
    return f"${cents // 100:,}"


@dataclass(frozen=True)
class CoverageRule:
    """The policy's exclusions, minimums, and the organization's name, read once."""

    excluded_categories: frozenset[str]
    excluded_airworthiness: frozenset[str]
    min_per_occurrence_cents: int
    min_per_person_cents: int
    organization: str

    def judge(self, aircraft: Aircraft) -> Coverage:
        """The coverage of ``aircraft``, from its category, airworthiness, and liability.

        A category or an airworthiness listed by the policy excludes the aircraft; when
        both are, the reason names the category.  A blank value is never listed, so an
        aircraft without either one recorded is never excluded by them.  Then a recorded
        policy (one with an ``insurance_expiration``) whose liability is under either
        minimum excludes it, naming the minimums it misses; an aircraft without a policy
        on file isn't judged on its liability, since there isn't a policy to fall short.
        Otherwise one without a category is answered with :data:`CATEGORY_NOT_RECORDED`.
        """
        if aircraft.category in self.excluded_categories:
            return self._excluded(CATEGORY_PLURALS[aircraft.category])
        if aircraft.airworthiness in self.excluded_airworthiness:
            return self._excluded(AIRWORTHINESS_PLURALS[aircraft.airworthiness])
        if aircraft.insurance_expiration is not None:
            missed = self.shortfall(
                per_occurrence_cents=aircraft.insurance_liability_per_occurrence_cents,
                per_person_cents=aircraft.insurance_liability_per_person_cents,
            )
            if missed:
                return Coverage(
                    excluded=True,
                    reason=(
                        f"Not covered: liability is under {self.organization}'s minimum of "
                        f"{' and '.join(missed.values())}"
                    ),
                )
        if aircraft.category == "":
            return Coverage(excluded=False, reason=CATEGORY_NOT_RECORDED)
        return Coverage(excluded=False, reason="")

    def shortfall(self, *, per_occurrence_cents: int, per_person_cents: int) -> dict[str, str]:
        """The minimums liability of these amounts misses, each worded for a reason.

        Keyed by the aircraft field that falls short, in the order per occurrence then
        per person, such as ``{"insurance_liability_per_occurrence_cents": "$1,000,000
        per occurrence"}``; empty when both amounts meet their minimums.
        """
        missed: dict[str, str] = {}
        if per_occurrence_cents < self.min_per_occurrence_cents:
            missed["insurance_liability_per_occurrence_cents"] = (
                f"{dollars(self.min_per_occurrence_cents)} per occurrence"
            )
        if per_person_cents < self.min_per_person_cents:
            missed["insurance_liability_per_person_cents"] = (
                f"{dollars(self.min_per_person_cents)} per person"
            )
        return missed

    def _excluded(self, what: str) -> Coverage:
        """An exclusion of ``what``, worded as the aircraft check prints it."""
        return Coverage(
            excluded=True,
            reason=f"Not covered: {what} are excluded by {self.organization}'s policy",
        )


def rule_for(policy: AircraftCoveragePolicy) -> CoverageRule:
    """The rule ``policy`` states, naming the organization from the site settings.

    A policy without an exclusion or a minimum never names the organization, so the
    site settings are read only when a reason could need them.
    """
    excludes_any = (
        len(policy.excluded_categories) + len(policy.excluded_airworthiness) > 0
        or policy.min_liability_per_occurrence_cents > 0
        or policy.min_liability_per_person_cents > 0
    )
    return CoverageRule(
        excluded_categories=frozenset(policy.excluded_categories),
        excluded_airworthiness=frozenset(policy.excluded_airworthiness),
        min_per_occurrence_cents=policy.min_liability_per_occurrence_cents,
        min_per_person_cents=policy.min_liability_per_person_cents,
        organization=org_details().name if excludes_any else "",
    )


def current_rule() -> CoverageRule:
    """The rule the stored policy states now (an empty policy when none is stored)."""
    return rule_for(AircraftCoveragePolicy.load())
