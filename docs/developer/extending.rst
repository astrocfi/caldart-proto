====================
Extending the system
====================

CalDART is built to grow in six places: a payment provider, an API endpoint, a
portal screen, a management command, a Wagtail page type and a StreamField
block.  Each recipe below names the base class to start from, the file the code
belongs in, how the system finds it, and the documentation page that changes
with it.

Every skeleton was pasted into the tree and put through ``ruff check`` and
``mypy``, or ``tsc`` and ESLint, before it was written down; a fragment showing
one class or one function assumes the imports its neighbors in that file
already have.  Rename the class, replace the bodies, and the surrounding
machinery works.  Nothing here is part of the shipping system: ``acme``, the
lapsed-insurance report and the handbook page are examples, not endpoints you
will find running.

Two rules apply to all six.  Every extension point is covered by a test in
``backend/tests/`` or beside its component (:doc:`testing`), and every one
changes a documentation page in the same pull request: the guide is the
specification, so code that outruns it is an unfinished change.


A payment provider
==================

A provider is a subclass of ``Provider`` from
``backend/apps/payments/providers/base.py``.  :doc:`payments-setup` describes
the three methods it must supply and the error types it may raise; this is the
shape of the module and everything that has to be told about it.

#. Read the credentials in ``backend/caldart/settings/base.py`` beside the
   Stripe and PayPal ones, and document each variable in ``.env.example``,
   ``deploy/caldart.env.example`` and :doc:`configuration`.  Do this first:
   django-stubs types the settings object from the settings module, so
   ``settings.ACME_SECRET_KEY`` fails ``mypy`` until the name exists.
#. Write ``backend/apps/payments/providers/<slug>.py``: subclass ``Provider``,
   set ``slug``, implement ``start``, ``confirm`` and ``handle_webhook``, and
   decorate the class with ``@register``.
#. Import the class in ``providers/__init__.py`` and add it to ``__all__``.
   Importing the package is what registers every provider, so nothing else has
   to know the module exists.
#. Add a branch to ``available_providers()`` in
   ``backend/apps/payments/providers/base.py`` that offers the slug once its
   settings are present.  ``GET /api/v1/payments/config`` reports that list, so
   this is what makes the tab appear at checkout.
#. Add the slug to ``PaymentProvider`` in ``backend/apps/payments/models.py``
   and run ``manage.py makemigrations payments``.  Add a ``PaymentWallet``
   value too if the provider reports a way of paying that the enum does not
   already carry.
#. Add the confirm and webhook routes to ``backend/apps/payments/api/urls.py``
   next to the Stripe and PayPal ones.  A webhook view sets
   ``authentication_classes`` and ``permission_classes`` to empty lists and
   carries ``@method_decorator(csrf_exempt, name="dispatch")``, as
   ``StripeWebhookView`` and ``PayPalWebhookView`` in
   ``backend/apps/payments/api/views.py`` do, because a provider posting from
   its own servers has no session and no CSRF token to send.  Nothing then
   stands between the provider and the view: the signature is the only proof of
   where the body came from, which is why the skeleton refuses one it cannot
   verify.
#. Write the checkout panel in
   ``frontend/src/portal/features/checkout/<Name>Panel.tsx`` and offer it from
   ``Checkout.tsx`` when the config lists the slug.
#. Cover it in ``backend/tests/test_payments_<slug>.py``: a successful charge,
   a mismatched amount, an unconfigured provider, and a webhook delivered
   twice.

.. code-block:: python

   """The Acme payment provider."""

   from __future__ import annotations

   import json
   import logging
   from typing import Any, TypedDict

   from django.conf import settings
   from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse

   from apps.payments.models import Payment, PaymentWallet
   from apps.payments.providers.base import (
       PaymentVerificationError,
       Provider,
       ProviderNotConfiguredError,
       register,
   )
   from apps.payments.services import mark_failed, mark_succeeded

   log = logging.getLogger(__name__)


   class AcmeCharge(TypedDict):
       """The fields this provider reads back from Acme."""

       id: str
       status: str
       amount_cents: int
       currency: str


   @register
   class AcmeProvider(Provider):
       """Takes payment through Acme's hosted checkout."""

       slug = "acme"

       def start(self, payment: Payment) -> dict[str, Any]:
           """Open a charge and return what the browser needs to present it."""
           charge = self._open_charge(payment)
           payment.provider_ref = charge["id"]
           payment.save(update_fields=["provider_ref", "updated_at"])
           return {"checkout_token": charge["id"]}

       def confirm(self, payment: Payment, **kwargs: Any) -> bool:
           """Read the charge back from Acme and settle the payment."""
           charge = self._read_charge(payment.provider_ref)
           self._verify(payment, charge)
           if charge["status"] != "paid":
               mark_failed(payment, dict(charge))
               return False
           mark_succeeded(
               payment,
               wallet=PaymentWallet.CARD,
               raw=dict(charge),
               provider_ref=charge["id"],
           )
           return True

       def handle_webhook(self, request: HttpRequest) -> HttpResponse:
           """Apply one Acme notification, idempotently.

           A ``charge.paid`` event for a known charge that Acme still reports at the
           recorded amount and currency activates the membership term; a
           ``charge.failed`` event marks the payment failed.  An unknown charge, a
           failed verification and every other event type are received but not
           handled.
           """
           if request.method != "POST":
               return HttpResponseNotAllowed(["POST"])
           if not self._signature_is_valid(request):
               return JsonResponse({"detail": "Invalid Acme signature."}, status=400)
           event = json.loads(request.body)
           event_type = str(event.get("type", ""))
           charge_id = str(event.get("charge_id", ""))
           payment = Payment.objects.filter(provider=self.slug, provider_ref=charge_id).first()
           if payment is None:
               log.info("Acme webhook named an unknown charge %s", charge_id)
               return JsonResponse({"received": True, "handled": False})
           if event_type == "charge.paid":
               charge = self._read_charge(charge_id)
               try:
                   self._verify(payment, charge)
               except PaymentVerificationError as exc:
                   log.error("Acme webhook verification failed: %s", exc)
                   return JsonResponse({"received": True, "handled": False})
               mark_succeeded(payment, wallet=PaymentWallet.CARD, raw=dict(charge))
           elif event_type == "charge.failed":
               mark_failed(payment, dict(event))
           else:
               return JsonResponse({"received": True, "handled": False})
           return JsonResponse({"received": True, "handled": True})

       def _verify(self, payment: Payment, charge: AcmeCharge) -> None:
           """Refuse a charge whose amount or currency is not the one we recorded."""
           if charge["amount_cents"] != payment.amount_cents:
               raise PaymentVerificationError("The Acme charge is for a different amount.")
           if charge["currency"] != payment.currency:
               raise PaymentVerificationError("The Acme charge is in a different currency.")

       def _secret_key(self) -> str:
           """The configured secret key, or ``ProviderNotConfiguredError``."""
           key: str = settings.ACME_SECRET_KEY
           if not key:
               raise ProviderNotConfiguredError("'acme' is not configured.")
           return key

       def _open_charge(self, payment: Payment) -> AcmeCharge:
           """Ask Acme for a new charge.  Replace with the vendor's SDK call."""
           raise NotImplementedError

       def _read_charge(self, charge_id: str) -> AcmeCharge:
           """Read one charge back from Acme.  Replace with the vendor's SDK call."""
           raise NotImplementedError

       def _signature_is_valid(self, request: HttpRequest) -> bool:
           """Check the webhook signature.  Replace with the vendor's SDK call."""
           raise NotImplementedError

The three helpers are the only places the vendor's library appears.  Each must
turn that library's exceptions into ``ProviderUnavailableError`` (and a missing
key into ``ProviderNotConfiguredError``), because the confirm view catches
``PaymentError`` and answers it with HTTP 400, while anything else becomes a
500.  The webhook view catches nothing: it hands the request straight to
``handle_webhook``, so the skeleton catches ``PaymentVerificationError`` itself
and answers 200 with ``handled: false``.  An exception that escapes there is a
500, which a provider reads as a failed delivery and retries, so a single
mismatched amount would arrive again and again.

``confirm`` and ``handle_webhook`` both reach the money through
``mark_succeeded``, which is idempotent, so a webhook that arrives after the
browser's confirmation is a no-op rather than a second membership term.

Never trust the notification body.  The skeleton settles nothing on the
strength of the event alone: it branches on the event type, reads the charge
back from Acme, and compares the amount and currency against the stored payment
before it activates a term.  A notification that reports anything other than a
paid charge must never reach ``mark_succeeded``.

**Documentation to change:** :doc:`payments-setup` (the provider list and the
go-live checklist), :doc:`api-payments` (the confirm and webhook endpoints),
:doc:`configuration` (the settings) and :doc:`/user/payments` if a member sees
a new way to pay.


An API endpoint
===============

Each app keeps its routes in ``backend/apps/<app>/api/urls.py``, and
``backend/caldart/api_urls.py`` already includes every one of them, so adding
an endpoint never edits the router.

#. Add or reuse a serializer in ``backend/apps/<app>/api/serializers.py``.
   Compute anything security-relevant — prices, roles, ownership — on the
   server; never read it from the request body.
#. Write the view in ``backend/apps/<app>/api/views.py``, with the permission
   classes the matrix in :ref:`api-permission-matrix` requires.  ``HasAnyRole``
   and ``HasRole`` from ``apps.accounts.permissions`` build a role check;
   object-level rules go in a ``BasePermission`` subclass in
   ``apps/<app>/api/permissions.py`` with a ``message`` the caller can act on.
#. Add the path to ``backend/apps/<app>/api/urls.py``.  Paths carry no trailing
   slash, and an administrative endpoint lives under ``admin/``.
#. Write ``backend/tests/test_<feature>.py`` covering each role that may call
   it and at least one that may not, asserting on the status code and the
   response body.
#. Add the response shape to ``frontend/src/portal/api/types.ts`` if it is one
   the portal has not seen before, and a query hook in the feature that calls
   it.

.. code-block:: python

   # backend/apps/aircraft/api/views.py

   class UninsuredAircraftView(generics.ListAPIView[Aircraft]):
       """``GET /admin/aircraft/uninsured`` -- the register's lapsed insurance."""

       serializer_class = AircraftSerializer
       permission_classes = [HasAnyRole(ACCOUNT_ADMIN)]

       def get_queryset(self) -> QuerySet[Aircraft]:
           """Aircraft whose insurance expired before today, longest lapsed first."""
           return Aircraft.objects.filter(insurance_expiration__lt=timezone.localdate()).order_by(
               "insurance_expiration"
           )

.. code-block:: python

   # backend/apps/aircraft/api/urls.py

   path(
       "admin/aircraft/uninsured",
       views.UninsuredAircraftView.as_view(),
       name="uninsured",
   ),

**Documentation to change:** the ``api-<area>.rst`` page for the endpoint's
area — a heading giving the method and path, who may call it, the request body
or query parameters, and every status it can answer with a JSON example — and
the permission matrix in :doc:`api-reference` when the roles change.  A new
area needs a new page in that page's ``toctree``.


A portal screen
===============

The portal is a React single-page application under
``frontend/src/portal/``.  A screen is four small files plus one line in each of
two shared ones, and those two shared files exist precisely so that parallel
work does not collide in the route table.

#. Write the queries in ``frontend/src/portal/features/<feature>/api.ts`` as
   TanStack Query hooks over ``api`` from ``api/client.ts``.  Give the feature
   a query-key constant so invalidation is spelled the same way everywhere.
#. Write the screen in
   ``frontend/src/portal/features/<feature>/<Name>Page.tsx``, building it from
   the primitives in ``frontend/src/portal/components/`` — ``Page``, ``Card``,
   ``DataTable``, ``EmptyState``, ``Loading``, ``StatusChip`` — rather than new
   markup.
#. Export a ``RouteObject[]`` from
   ``frontend/src/portal/routes/<feature>.tsx``, wrapped in ``RequireRole``
   when it is not for every member, and load the component with ``lazy`` so its
   code arrives only when somebody opens the screen.
#. Add that array to ``privateRoutes`` (or ``publicRoutes``) in
   ``routes/index.tsx``, which does nothing but concatenate the feature files.
#. Declare the navigation entry in ``frontend/src/portal/nav.ts``.  An entry
   with no ``NAV_ITEMS`` row is reachable by URL alone, which is how a screen
   ends up invisible.
#. Write ``<Name>Page.test.tsx`` beside the component, rendering through
   ``src/test/render.tsx`` and answering the API from the msw server in
   ``src/test/server.ts``.

.. code-block:: ts

   // frontend/src/portal/features/uninsured/api.ts
   export const UNINSURED_KEY = 'uninsured-aircraft';

   /** Aircraft whose insurance has lapsed, via `GET /admin/aircraft/uninsured`. */
   export function useUninsuredAircraft(): UseQueryResult<Aircraft[]> {
     return useQuery({
       queryKey: [UNINSURED_KEY],
       queryFn: () => api.get<Aircraft[]>('/admin/aircraft/uninsured'),
     });
   }

.. code-block:: tsx

   // frontend/src/portal/features/uninsured/UninsuredPage.tsx

   /** Lists the lapsed-insurance aircraft, longest lapsed first. */
   export function UninsuredPage(): JSX.Element {
     const query = useUninsuredAircraft();

     return (
       <Page title="Lapsed insurance" eyebrow="Aircraft" lede="Airframes to chase.">
         {query.isPending ? <Loading /> : null}
         {query.data?.length === 0 ? <EmptyState title="Every aircraft is insured." /> : null}
         {query.data?.map((aircraft) => (
           <Card key={aircraft.id} title={aircraft.n_number}>
             <p className="muted">{aircraft.insurance_summary}</p>
           </Card>
         ))}
       </Page>
     );
   }

.. code-block:: tsx

   // frontend/src/portal/routes/uninsured.tsx
   export const uninsuredRoutes: RouteObject[] = [
     {
       element: <RequireRole roles={['account_admin']} />,
       children: [
         {
           path: 'admin/aircraft/uninsured',
           lazy: async () => ({
             Component: (await import('../features/uninsured/UninsuredPage')).UninsuredPage,
           }),
         },
       ],
     },
   ];

.. code-block:: ts

   // frontend/src/portal/nav.ts, inside NAV_ITEMS
   {
     to: '/admin/aircraft/uninsured',
     label: 'Lapsed insurance',
     roles: ['account_admin'],
     group: 'Administration',
   },

``RequireRole`` and the ``NAV_ITEMS`` entry must name the same roles as the
endpoint's permission classes.  When they disagree the screen either hides
itself from people entitled to it or renders and then fails every request with
a 403.

**Documentation to change:** the chapter of the :doc:`/user/index` for the role
that sees the screen, quoting the labels exactly as the page shows them, and
:doc:`architecture` if the screen adds a new feature directory.


A management command
====================

Commands live in ``backend/apps/<app>/management/commands/<name>.py`` and
Django finds them by that path alone.

#. Subclass ``BaseCommand``, set ``help`` to one sentence — it is what
   ``manage.py help`` prints — and register options in ``add_arguments``.
#. Raise ``CommandError`` for anything an operator can act on: it exits
   non-zero with the message and no traceback, which is what a systemd timer
   reads as a failed run.  Never call ``print``; write through ``self.stdout``
   and ``self.stderr``, and ``self.style`` for color.
#. Make it safe to run twice.  An operator will.
#. Add a row to the management-command table in :doc:`setup`, and a ``make``
   target when operators run it routinely.
#. Cover it in ``backend/tests/test_<feature>.py`` with ``call_command`` and a
   ``StringIO`` passed as ``stdout``, asserting on the exact output and on the
   ``CommandError`` message for bad input.

.. code-block:: python

   """``manage.py list_uninsured_aircraft`` -- the register's lapsed insurance.

   Run by hand before a callout.  Reads the aircraft register and writes nothing,
   so it is safe to repeat.
   """

   from __future__ import annotations

   import argparse
   from datetime import date
   from typing import Any

   from django.core.management.base import BaseCommand, CommandError
   from django.utils import timezone

   from apps.aircraft.models import Aircraft


   class Command(BaseCommand):
       """Lists every aircraft whose insurance expired before a given date."""

       help = "List aircraft whose insurance has lapsed."

       def add_arguments(self, parser: argparse.ArgumentParser) -> None:
           """Register ``--as-of`` on the command's argument parser."""
           parser.add_argument(
               "--as-of",
               metavar="YYYY-MM-DD",
               help="Judge currency against this date instead of today.",
           )

       def handle(self, *args: Any, **options: Any) -> None:
           """Print one line per lapsed aircraft, then a count.

           ``--as-of`` must be an ISO ``YYYY-MM-DD`` date, or ``CommandError`` is raised
           with the invalid value quoted.
           """
           as_of = timezone.localdate()
           if options["as_of"]:
               try:
                   as_of = date.fromisoformat(options["as_of"])
               except ValueError as exc:
                   raise CommandError(f"--as-of must be YYYY-MM-DD, not {options['as_of']!r}") from exc

           lapsed = Aircraft.objects.filter(insurance_expiration__lt=as_of).order_by("n_number")
           for aircraft in lapsed:
               self.stdout.write(f"{aircraft.n_number}  expired {aircraft.insurance_expiration}")
           self.stdout.write(self.style.SUCCESS(f"{lapsed.count()} with lapsed insurance"))

``argparse`` turns ``--as-of`` into the ``as_of`` key of ``options``, and the
key is always present, so read it directly rather than through ``getattr``.

**Documentation to change:** the management-command table in :doc:`setup`, the
make-target table there when the command gets a wrapper, and the operator
chapter of the :doc:`/user/index` when an administrator is the one running it.


.. _extending-page-type:

A Wagtail page type
===================

Page types are Django models in ``backend/apps/cms/models.py``.  :doc:`cms`
describes the existing tree and what ``BasePage`` and ``MembersOnlyMixin``
supply.

#. Subclass ``BasePage``, and list ``MembersOnlyMixin`` first in the bases when
   the page can be closed to non-members.
#. Declare ``content_panels``, ``search_fields``, ``template``, and
   ``parent_page_types`` / ``subpage_types`` so editors cannot build a
   nonsensical tree.
#. Give ``Meta`` a ``verbose_name``, which is how Wagtail's "add a child page"
   chooser names it.  A ``__str__`` is optional: Wagtail's ``Page`` already
   returns the page title.
#. Write ``backend/templates/cms/<snake_name>.html`` extending ``base.html``,
   and use the semantic tokens rather than introducing colors
   (:doc:`theming`).
#. ``manage.py makemigrations cms``.
#. Extend ``seed_content`` if the example site should carry one.
#. Cover it in ``backend/tests/test_cms_pages.py``: that it renders, and that
   its access rules behave.

.. code-block:: python

   # backend/apps/cms/models.py

   class HandbookPage(MembersOnlyMixin, BasePage):
       """A DART handbook: an intro, a body, and the members-only switch."""

       intro = models.TextField(blank=True, help_text="One or two sentences under the title.")
       body = StreamField(ContentStreamBlock(), blank=True)

       content_panels = [
           *Page.content_panels,
           FieldPanel("intro"),
           FieldPanel("body"),
           MultiFieldPanel(MembersOnlyMixin.members_only_panels, heading="Access"),
       ]

       search_fields = [
           *Page.search_fields,
           index.SearchField("intro"),
           index.SearchField("body"),
           index.FilterField("members_only"),
       ]

       template = "cms/handbook_page.html"
       parent_page_types = ["cms.StandardPage"]
       subpage_types: list[str] = []

       class Meta:
           verbose_name = "handbook page"

**Documentation to change:** the page-model table in :doc:`cms`, the Wagtail
section of :doc:`data-model`, and the website-administrator chapter of the
:doc:`/user/index`.


.. _extending-block:

A StreamField block
===================

Blocks live in ``backend/apps/cms/blocks.py``.  ``ContentStreamBlock`` is the
body offered on every editable page and ``ColumnStreamBlock`` the reduced set
allowed inside a two-column block.

#. Write the block class, with a ``Meta`` that sets ``icon``, ``label`` and
   ``template``.
#. Add it to ``ContentStreamBlock``, and to ``ColumnStreamBlock`` when it makes
   sense inside a column.
#. Write ``backend/templates/cms/blocks/<name>.html``.  Use the semantic
   tokens; do not introduce colors (:doc:`theming`).
#. Style it in ``frontend/src/styles/site.css``.
#. ``manage.py makemigrations cms`` — a StreamField change is a migration even
   though the column type does not change.
#. Cover it in ``backend/tests/test_cms_pages.py``; the
   ``test_standard_page_renders_every_block_type`` test builds one of each.
#. Add the block's name to ``RESTRICTED_BLOCK_TYPES`` if only website
   administrators may use it.

.. code-block:: python

   # backend/apps/cms/blocks.py

   class StatBlock(blocks.StructBlock):
       """One headline number with a label under it."""

       value = blocks.CharBlock(max_length=20, help_text="For example 128 or 4,500 lb.")
       label = blocks.CharBlock(max_length=80)
       note = blocks.CharBlock(required=False, max_length=160)

       class Meta:
           icon = "table"
           label = "Statistic"
           template = "cms/blocks/stat.html"

.. code-block:: python

   # backend/apps/cms/blocks.py, inside ContentStreamBlock

   stat = StatBlock()

**Documentation to change:** the block list in :doc:`cms`, and the
website-administrator chapter of the :doc:`/user/index` where the editor's
palette is described.


Related
=======

:doc:`architecture` is the map of the whole system, :doc:`testing` covers the
gates every one of these recipes must pass, and the subsystem chapters —
:doc:`payments-setup`, :doc:`cms`, :doc:`theming`, :doc:`reports` and
:doc:`reminders` — carry the contracts these recipes extend.
