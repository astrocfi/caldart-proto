"""Scheduled charges: the standing authority, the scanner, and its emails.

Somebody who asks CalDART to charge them on a schedule gives it a *mandate*: a
payment method saved with their provider, together with what it pays for.  A
mandate comes in two kinds, and a person holds at most one of each: an
**automatic renewal** names a plan and renews the membership once a year, with a
contribution beside the dues if they chose one, and a **recurring donation** names
no plan and gives a contribution alone, monthly, quarterly or yearly.  Nothing
about the schedule lives at the provider -- no Stripe subscription, no PayPal
billing plan -- so the plan, the price, the term, the cadence and the reminder
logic all stay here, in one place.

The package is split by concern, and ``__init__`` re-exports nothing: import each name
from the module that defines it.

- ``schedule``: what a mandate is and when it charges -- ``MandateKind``, the
  amount, the term it renews and its charge dates.
- ``emails``: the subjects, the shared template context and the one send function.
- ``mandates``: setting a mandate up, saving its method, changing it and turning it
  off, and the rule that a contribution lives in one place.
- ``scan``: ``run_auto_renewals``, the daily scan that sends the notices and takes
  the charges.

Each module imports only from the ones listed before it, so the package has no cycle.
"""
