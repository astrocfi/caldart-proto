"""``manage.py seed_content`` — the example CalDART site.

Builds this page tree::

    Home
      About Us
        History
        DARTs                (index + one page per DART)
        Directors and Officers
      News                   (index + three posts)
      Join CalDART
      Donate
      Sponsors
      Contact Us
      Members                (members only)
        Members Only
        Documents and Links

Idempotent: every page is looked up by slug under its parent and updated in
place, so running the command twice leaves exactly the same tree.  All copy is
*example content* — paraphrased from the public CalDART site, not lifted from
it — and any website administrator can replace it from ``/admin/``.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.cms.models import (
    ContactPage,
    DartIndexPage,
    DartPage,
    HomePage,
    NewsIndexPage,
    NewsPage,
    StandardPage,
)
from apps.cms.permissions import grant_website_admin_permissions
from apps.cms.seed import ensure_site_root
from apps.members.models import Dart
from apps.members.seed import seed_darts

# ---------------------------------------------------------------------------
# Copy
# ---------------------------------------------------------------------------

HERO_HEADING = "Volunteer air transportation when California needs it"
HERO_LEDE = (
    "CalDART organizes pilots, aircraft owners and ground crews into local teams so that "
    "when an earthquake, wildfire or flood cuts a community off, relief supplies, people "
    "and information keep moving."
)

MISSION = (
    "<p>CalDART exists to give California's emergency managers a trained, insured and "
    "practiced volunteer air transportation capability — organized before the disaster, "
    "not improvised during it.</p>"
)

CONCEPT_STEPS: tuple[tuple[str, str], ...] = (
    (
        "Local teams form around an airport",
        "A DART — Disaster Airlift Response Team — is a group of pilots, aircraft owners "
        "and ground volunteers based at one general aviation airport. The airport is the "
        "unit of organization because that is where the aircraft, fuel and ramp space are.",
    ),
    (
        "Members stay current, all year",
        "Membership means keeping a certificate, a medical and — for aircraft owners — "
        "liability insurance current, and keeping that information where a DART leader can "
        "check it in seconds.",
    ),
    (
        "We train with the agencies we will fly for",
        "Teams run exercises with county offices of emergency services, CERT groups and "
        "other volunteer organizations, so the paperwork, radios and load plans are "
        "familiar before they matter.",
    ),
    (
        "A county activates its DART",
        "Requests come through the county emergency operations center. The DART leader "
        "calls out the members whose aircraft, currency and availability fit the mission.",
    ),
    (
        "Small aircraft move small, urgent loads",
        "Blood products, medications, radios, damage-assessment teams and communications "
        "volunteers — the loads that are too small for a military airlift and too urgent "
        "for a closed highway.",
    ),
)

TAX_STATUS = (
    "<p>CalDART is a California non-profit corporation and a 501(c)(3) public charity. "
    "Membership dues and contributions are tax deductible to the extent allowed by law. "
    "Members fly at their own expense as volunteers.</p>"
)

ABOUT_INTRO = (
    "CalDART is a statewide network of local Disaster Airlift Response Teams. We recruit, "
    "organize and train general aviation volunteers so California counties have an air "
    "transportation option that does not have to be invented on the day of the disaster."
)

HISTORY_INTRO = (
    "CalDART grew out of a single Bay Area airport exercise into a statewide network. "
    "These are the milestones that got us here."
)

HISTORY_MILESTONES: tuple[tuple[str, str], ...] = (
    (
        "2011",
        "Volunteers at a Bay Area general aviation airport run the first Disaster Airlift "
        "Response Team exercise, flying simulated relief loads between two fields.",
    ),
    (
        "2013",
        "A second and third airport stand up teams of their own. The founding volunteers "
        "publish the first DART organizing handbook so a new airport does not have to "
        "start from a blank page.",
    ),
    (
        "2015",
        "CalDART incorporates as a California non-profit to hold the network together, "
        "share training material and speak to counties with one voice.",
    ),
    (
        "2016",
        "The IRS recognizes CalDART as a 501(c)(3) public charity. Dues and contributions "
        "become tax deductible.",
    ),
    (
        "2017",
        "The North Bay fires make the case in the worst possible way. Teams fly "
        "damage-assessment and communications volunteers, and the network doubles in the "
        "twelve months that follow.",
    ),
    (
        "2019",
        "Public safety power shut-offs prompt joint exercises with county offices of "
        "emergency services and amateur radio groups across Northern California.",
    ),
    (
        "2020",
        "Exercises move online and onto individual airports. Members fly medical supply "
        "runs for county public health departments through the pandemic year.",
    ),
    (
        "2021",
        "The network reaches Southern and Central California with new teams on the coast "
        "and in the Los Angeles basin.",
    ),
    (
        "2022",
        "Sixteen DARTs are organized across the state, and the member roster, aircraft "
        "insurance records and training history move into one shared system.",
    ),
)

DARTS_INTRO = (
    "Every DART is built around a general aviation airport and led by volunteers who fly "
    "from it. Find the team nearest you, or join as unaffiliated and we will introduce you "
    "to the closest leader."
)

#: Leader names for the example DART pages — invented, not real people.
DART_LEADERS: tuple[str, ...] = (
    "Helen Marchetti",
    "Victor Ocampo",
    "Dana Whitfield",
    "Samuel Oyelaran",
    "Rosa Villanueva",
    "Keith Brannigan",
    "Aiko Tanaka",
    "Miles Gutierrez",
    "Priya Raman",
    "Elena Sokolov",
    "Gordon Achebe",
    "Teresa Lindqvist",
    "Marcus Delgado",
    "Nadia Farouk",
    "Owen Castellanos",
    "Joan Petrakis",
)

DIRECTORS_INTRO = (
    "CalDART is run by a volunteer board elected by the membership. Directors serve "
    "two-year terms; officers are elected by the board each January."
)

DIRECTORS: tuple[tuple[str, str], ...] = (
    ("President", "Helen Marchetti — Napa DART, commercial pilot and former county OES planner"),
    ("Vice President", "Samuel Oyelaran — Hayward DART, CFII and exercise coordinator"),
    ("Secretary", "Teresa Lindqvist — Santa Rosa DART, aircraft owner and CERT instructor"),
    ("Treasurer", "Marcus Delgado — Reid-Hillview DART, CPA and private pilot"),
    ("Director at large", "Aiko Tanaka — Monterey DART, ground team lead"),
    ("Director at large", "Gordon Achebe — San Carlos DART, ATP and safety officer"),
    ("Director at large", "Rosa Villanueva — Livermore DART, communications lead"),
)

NEWS_POSTS: tuple[dict, ...] = (
    {
        "slug": "statewide-exercise-moves-simulated-relief-loads",
        "title": "Statewide exercise moves simulated relief loads between nine airports",
        "days_ago": 12,
        "intro": (
            "Twenty-eight aircraft and more than sixty ground volunteers took part in this "
            "year's multi-county exercise."
        ),
        "body": (
            "<p>Nine DARTs flew a coordinated exercise on Saturday, moving palletized "
            "“relief supplies” — in practice, sandbags and marked cartons — between airports "
            "on a schedule set by a simulated county emergency operations center.</p>"
            "<p>The scenario assumed a magnitude 6.8 earthquake had closed two state "
            "highways. Ground teams handled manifests, weight and balance checks and "
            "hand-offs to CERT volunteers at the receiving fields, while amateur radio "
            "operators passed traffic between the airports and the exercise EOC.</p>"
            "<p>Debrief notes and the load-planning worksheets are in the members' area.</p>"
        ),
        "quote": (
            "The point of the exercise is the paperwork and the radios, not the flying. "
            "The flying is the easy part.",
            "Exercise coordinator, CalDART",
        ),
    },
    {
        "slug": "two-new-darts-in-the-central-valley",
        "title": "Two new teams stand up in the Central Valley",
        "days_ago": 41,
        "intro": (
            "Pilots at two inland airports have completed the organizing checklist and are "
            "recruiting members."
        ),
        "body": (
            "<p>Both airports ran their first tabletop exercise with county emergency "
            "management last month and have started signing up pilots, aircraft owners and "
            "ground volunteers.</p>"
            "<p>Standing up a DART takes a core of four or five committed volunteers, a "
            "conversation with the airport manager and a county contact willing to take the "
            "call. If that sounds like your field, the organizing handbook is in the "
            "members' area and a board member will walk you through it.</p>"
        ),
    },
    {
        "slug": "insurance-and-currency-records-move-online",
        "title": "Membership, medical and insurance records move online",
        "days_ago": 96,
        "intro": (
            "DART leaders can now check a member's currency from a phone on the ramp, "
            "instead of a spreadsheet emailed once a quarter."
        ),
        "body": (
            "<p>Members keep their own profile up to date: contact details, certificate and "
            "medical, the aircraft they commonly fly, and the volunteer roles they are "
            "willing to take on. Aircraft owners record their liability limits and policy "
            "expiry once, and every pilot attached to that aircraft benefits.</p>"
            "<p>Renewal reminders go out at sixty, thirty and seven days. Nobody has to "
            "chase a lapsed medical by hand any more.</p>"
        ),
    },
)

JOIN_INTRO = (
    "Membership is open to anyone willing to help — you do not need to be a pilot, and you "
    "do not need to own an aircraft."
)

DONATE_INTRO = (
    "Dues cover the basics. Contributions pay for the exercises, radios, training material "
    "and insurance that make a DART useful to a county on the worst day of its year."
)

CONTRIBUTION_TIERS: tuple[tuple[str, str], ...] = (
    ("$20 — Participating", "Covers a member's share of exercise materials for a year."),
    ("$100 — Bronze", "Buys handheld radio batteries and cargo restraint for one team."),
    ("$300 — Silver", "Funds a tabletop exercise with a county emergency operations center."),
    ("$1,000 — Gold", "Underwrites a full multi-airport airlift exercise."),
    ("$3,000 — Diamond", "Equips a new DART with its ground team kit from scratch."),
    ("$10,000 — Platinum", "Sponsors a season of statewide training and outreach."),
)

SPONSORS_INTRO = (
    "CalDART's work is supported by flying clubs, fixed-base operators, avionics shops and "
    "businesses across California. Sponsors are listed here with their permission; nothing "
    "on this page is a paid endorsement."
)

SPONSOR_ROWS: tuple[tuple[str, str], ...] = (
    ("Bay Meridian Aviation", "Fixed-base operator — donated ramp space and fuel for exercises."),
    (
        "Sierra Avionics Works",
        "Avionics shop — discounted ADS-B and radio installations for members.",
    ),
    ("Golden Poppy Flying Club", "Flying club — aircraft made available for training weekends."),
    ("Coast Range Insurance Brokers", "Broker — guidance on volunteer liability cover."),
    ("Delta Fuel & Line Service", "Line service — fuel discounts on exercise days."),
)

CONTACT_INTRO = (
    "<p>The fastest way to reach us is email. Messages go to the board and are usually "
    "answered within a few days by a volunteer — please be patient, nobody here is paid.</p>"
    "<p>If you want to join a specific team, say which airport you fly from and we will put "
    "you in touch with that DART's leader directly.</p>"
)

MEMBERS_INTRO = (
    "Handbooks, exercise material, forms and the current roster. This area is open to "
    "members with a current membership, and to DART leaders and administrators."
)


# ---------------------------------------------------------------------------
# Page helpers
# ---------------------------------------------------------------------------


def rich(html: str) -> tuple[str, str]:
    return ("paragraph", html)


def heading(text: str, level: str = "h2") -> tuple[str, dict]:
    return ("heading", {"text": text, "level": level})


def quote(text: str, attribution: str = "") -> tuple[str, dict]:
    return ("quote", {"quote": text, "attribution": attribution})


def cta(label: str, url: str, style: str = "primary", note: str = "") -> tuple[str, dict]:
    return ("cta", {"label": label, "url": url, "style": style, "note": note})


def definition_list(rows) -> str:
    """Rich-text markup for a term/description list, which the blocks allow."""
    items = "".join(f"<li><b>{term}</b> — {text}</li>" for term, text in rows)
    return f"<ul>{items}</ul>"


def upsert_page(parent, model, slug: str, *, title: str, show_in_menus: bool = False, **fields):
    """Create or update ``slug`` under ``parent`` and publish it."""
    page = model.objects.child_of(parent).filter(slug=slug).first()
    if page is None:
        page = model(title=title, slug=slug, show_in_menus=show_in_menus)
        for key, value in fields.items():
            setattr(page, key, value)
        parent.add_child(instance=page)
    else:
        page.title = title
        page.show_in_menus = show_in_menus
        for key, value in fields.items():
            setattr(page, key, value)
        page.save()
    page.save_revision().publish()
    return model.objects.get(pk=page.pk)


# ---------------------------------------------------------------------------
# The tree
# ---------------------------------------------------------------------------


def seed_home(home: HomePage, about_url: str = "/about/") -> HomePage:
    home.hero_heading = HERO_HEADING
    home.hero_lede = HERO_LEDE
    home.primary_cta_label = "Join CalDART"
    home.primary_cta_url = "/portal/join"
    home.secondary_cta_label = "How we operate"
    home.secondary_cta_url = about_url
    home.mission_statement = MISSION
    home.concept_heading = "Organized before the emergency, not during it"
    home.concept_of_operations = [
        ("step", {"title": title, "text": text}) for title, text in CONCEPT_STEPS
    ]
    home.tax_status = TAX_STATUS
    home.save()
    home.save_revision().publish()
    return HomePage.objects.get(pk=home.pk)


def seed_about(home: HomePage) -> StandardPage:
    return upsert_page(
        home,
        StandardPage,
        "about",
        title="About Us",
        show_in_menus=True,
        intro=ABOUT_INTRO,
        body=[
            heading("What a DART is"),
            rich(
                "<p>A Disaster Airlift Response Team is a group of general aviation "
                "volunteers organized around one airport. Pilots fly. Aircraft owners "
                "provide the aircraft and keep the insurance current. Ground volunteers "
                "handle manifests, loading, radios and the hand-off at each end. Nobody is "
                "paid, and no member is ever obliged to fly a mission they judge unsafe.</p>"
            ),
            heading("What we are not"),
            rich(
                "<p>CalDART is not a first-responder agency and does not self-deploy. Teams "
                "fly when a county emergency manager asks for them, under that county's "
                "incident command. We are not a substitute for military airlift, air "
                "ambulance or firefighting aircraft; we carry the small, urgent loads those "
                "resources are not sized for.</p>"
            ),
            quote(
                "A Cessna with two hundred pounds of blood products on board is not "
                "glamorous. On day two of a closed highway it is the whole logistics chain.",
                "CalDART founding volunteer",
            ),
            heading("How the network is organized"),
            rich(
                "<p>Each DART runs its own recruiting, training and call-out list. CalDART "
                "holds the network together: shared handbooks and checklists, statewide "
                "exercises, one membership and insurance record system, and a single point "
                "of contact for agencies that want to work with general aviation "
                "volunteers.</p>"
            ),
            cta("Find your DART", "/about/darts/", "secondary"),
        ],
    )


def seed_history(about: StandardPage) -> StandardPage:
    return upsert_page(
        about,
        StandardPage,
        "history",
        title="History",
        intro=HISTORY_INTRO,
        body=[
            heading("How CalDART began"),
            rich(
                "<p>The idea is older than the organization. Pilots have flown relief loads "
                "after California disasters for decades — ad hoc, uninsured and usually "
                "unwelcome, because no county emergency manager wants unvetted aircraft "
                "arriving at a damaged airport. The DART model answered that objection: "
                "organize first, train with the agency, and show up with the paperwork "
                "already done.</p>"
            ),
            heading("Milestones"),
            rich(definition_list(HISTORY_MILESTONES)),
            heading("Where we are now"),
            rich(
                "<p>Sixteen teams, several hundred members, and a standing invitation to any "
                "California airport that wants to organize one. The bottleneck has never "
                "been aircraft; it is volunteers willing to do the unglamorous organizing "
                "work between disasters.</p>"
            ),
            cta("Join CalDART", "/portal/join", "primary", "Annual membership is $45."),
        ],
    )


def seed_darts_section(about: StandardPage) -> DartIndexPage:
    index = upsert_page(
        about,
        DartIndexPage,
        "darts",
        title="DARTs",
        intro=DARTS_INTRO,
        body=[
            heading("Starting a new team"),
            rich(
                "<p>If your airport has no DART, it takes four or five committed volunteers "
                "to start one. Get in touch and a board member will send you the organizing "
                "handbook and introduce you to a nearby leader who has done it.</p>"
            ),
            cta("Contact us", "/contact/", "secondary"),
        ],
    )

    darts = list(Dart.objects.order_by("sort_order", "name"))
    wanted: set[str] = set()
    for position, dart in enumerate(darts):
        leader = DART_LEADERS[position % len(DART_LEADERS)]
        contact = "{}@caldart.example.org".format(leader.lower().replace(" ", ".").replace("'", ""))
        where = (
            f"{dart.city} ({dart.airport_identifier})"
            if dart.airport_identifier
            else "no fixed home airport"
        )
        if dart.airport_identifier:
            summary = (
                f"<p>The {dart.name} DART flies from {where}. Members meet monthly, train "
                f"with {dart.city or 'their'} county emergency services, and take part in "
                "the statewide airlift exercise each year.</p>"
            )
        else:
            summary = (
                "<p>Not every member lives within reach of an organized team. Unaffiliated "
                "members carry a full CalDART membership, receive the same training material "
                "and are called on by the nearest DART when a mission fits.</p>"
            )
        slug = dart.airport_identifier.lower() if dart.airport_identifier else slugify(dart.name)
        wanted.add(slug)
        upsert_page(
            index,
            DartPage,
            slug,
            title=dart.name,
            dart=dart,
            leader_name=leader,
            leader_contact=contact,
            body=[
                rich(summary),
                heading("Who we need"),
                rich(
                    "<ul><li>Pilots with a current certificate and medical</li>"
                    "<li>Aircraft owners willing to make an aircraft available</li>"
                    "<li>Ground volunteers for manifests, loading and radios</li>"
                    "<li>Amateur radio operators</li></ul>"
                ),
                cta("Join this DART", "/portal/join", "primary"),
            ],
        )

    # A DART that has been renamed or removed leaves a page behind; drop it so
    # re-seeding converges on exactly one page per team.
    for stale in DartPage.objects.child_of(index).exclude(slug__in=wanted):
        stale.delete()

    return index


def seed_directors(about: StandardPage) -> StandardPage:
    return upsert_page(
        about,
        StandardPage,
        "directors",
        title="Directors and Officers",
        intro=DIRECTORS_INTRO,
        body=[
            heading("Board"),
            rich(definition_list(DIRECTORS)),
            heading("Meetings"),
            rich(
                "<p>The board meets by video call on the second Tuesday of each month. "
                "Members are welcome; ask the secretary for the link. Minutes are posted in "
                "the members' area.</p>"
            ),
        ],
    )


def seed_news(home: HomePage) -> NewsIndexPage:
    index = upsert_page(
        home,
        NewsIndexPage,
        "news",
        title="News",
        show_in_menus=True,
        intro="Exercises, new teams, and what the network has been doing.",
    )
    today = timezone.localdate()
    for post in NEWS_POSTS:
        body: list = [rich(post["body"])]
        if "quote" in post:
            body.append(quote(*post["quote"]))
        upsert_page(
            index,
            NewsPage,
            post["slug"],
            title=post["title"],
            date=today - timedelta(days=post["days_ago"]),
            intro=post["intro"],
            body=body,
        )
    return index


def seed_join(home: HomePage) -> StandardPage:
    return upsert_page(
        home,
        StandardPage,
        "join",
        title="Join CalDART",
        show_in_menus=True,
        intro=JOIN_INTRO,
        body=[
            heading("Dues"),
            rich(
                "<ul>"
                "<li><b>Annual membership — $45</b>, good for one year from the day it is "
                "paid.</li>"
                "<li><b>Life membership — $650</b>, paid once, never renewed.</li>"
                "</ul>"
                "<p>Dues are tax deductible. If the fee is a hardship, say so when you apply — "
                "we have never turned away a willing volunteer over $45.</p>"
            ),
            heading("Who is eligible"),
            rich(
                "<ul>"
                "<li>You are 18 or older.</li>"
                "<li>You live in, or regularly fly in, California.</li>"
                "<li>You agree to CalDART's safety policy and to flying only within your own "
                "and your aircraft's limits.</li>"
                "<li><b>Pilots</b> hold a current FAA certificate and a current medical or "
                "BasicMed, and record both in their member profile.</li>"
                "<li><b>Aircraft owners</b> carry liability insurance and record the carrier, "
                "limits and expiry date. Aircraft without current insurance are not "
                "dispatched.</li>"
                "<li><b>Ground volunteers</b> need no certificate at all — only the "
                "willingness to turn up.</li>"
                "</ul>"
            ),
            heading("What happens next"),
            rich(
                "<p>You create an account, fill in your profile, and pay by card, Apple Pay, "
                "Google Pay or PayPal. Your membership is active the moment the payment "
                "clears — there is no waiting period and no approval queue. A DART leader "
                "near you will be in touch about the next meeting.</p>"
            ),
            cta(
                "Start your membership",
                "/portal/join",
                "primary",
                "$45 annual or $650 life · card, Apple Pay, Google Pay or PayPal",
            ),
        ],
    )


def seed_donate(home: HomePage) -> StandardPage:
    return upsert_page(
        home,
        StandardPage,
        "donate",
        title="Donate",
        show_in_menus=True,
        intro=DONATE_INTRO,
        body=[
            heading("Contribution levels"),
            rich(definition_list(CONTRIBUTION_TIERS)),
            rich(
                "<p>Any amount helps, and you can add a contribution to your dues when you "
                "join or renew — one payment, one receipt.</p>"
            ),
            heading("Other ways to give"),
            rich(
                "<ul>"
                "<li><b>Employer matching</b> — many California employers match charitable "
                "gifts. Ask us for our EIN and determination letter.</li>"
                "<li><b>In kind</b> — fuel, hangar space, radios, cargo restraint and "
                "avionics work are all as useful as cash.</li>"
                "<li><b>Sponsorship</b> — businesses that support a season of training are "
                "listed on our sponsors page.</li>"
                "</ul>"
            ),
            cta("Give with your renewal", "/portal/renew", "secondary"),
        ],
    )


def seed_sponsors(home: HomePage) -> StandardPage:
    return upsert_page(
        home,
        StandardPage,
        "sponsors",
        title="Sponsors",
        intro=SPONSORS_INTRO,
        body=[
            heading("This year's supporters"),
            rich(definition_list(SPONSOR_ROWS)),
            heading("Becoming a sponsor"),
            rich(
                "<p>If your business serves general aviation in California and you would "
                "like to support a season of exercises, write to us. Sponsorship is "
                "acknowledged on this page and in the newsletter; it buys no influence over "
                "who we fly for.</p>"
            ),
            cta("Talk to us about sponsorship", "/contact/", "secondary"),
        ],
    )


def seed_contact(home: HomePage) -> ContactPage:
    return upsert_page(
        home,
        ContactPage,
        "contact",
        title="Contact Us",
        show_in_menus=True,
        intro=CONTACT_INTRO,
        body=[
            heading("Media enquiries"),
            rich(
                "<p>Please email rather than calling. A board member will respond, and we "
                "will happily put you in touch with a DART leader in your area.</p>"
            ),
            heading("Already a member?"),
            rich(
                "<p>Membership questions — renewals, receipts, a change of address — are "
                "fastest through the member portal.</p>"
            ),
            cta("Open the member portal", "/portal/", "quiet"),
        ],
    )


def seed_members_area(home: HomePage) -> StandardPage:
    members = upsert_page(
        home,
        StandardPage,
        "members",
        title="Members",
        show_in_menus=True,
        members_only=True,
        intro=MEMBERS_INTRO,
        body=[
            heading("What is in here"),
            rich(
                "<ul>"
                "<li>The DART organizing handbook and exercise playbooks</li>"
                "<li>Load planning worksheets and manifest forms</li>"
                "<li>Board minutes and the annual report</li>"
                "<li>The current roster and DART leader contact list</li>"
                "</ul>"
            ),
        ],
    )

    upsert_page(
        members,
        StandardPage,
        "members-only",
        title="Members Only",
        members_only=True,
        intro="Notices for current members, posted by the board and by DART leaders.",
        body=[
            heading("Next statewide exercise"),
            rich(
                "<p>Briefing packets go out four weeks ahead. Tell your DART leader whether "
                "you are flying, crewing on the ground or unavailable, so the load plan can "
                "be built against real aircraft.</p>"
            ),
            heading("Keep your record current"),
            rich(
                "<p>Check your medical and flight review dates in the portal, and — if you "
                "own the aircraft you fly — your insurance expiry. A DART leader checks "
                "these before dispatching you, and a lapsed date is the most common reason a "
                "willing member sits out a mission.</p>"
            ),
            cta("Check my profile", "/portal/profile", "secondary"),
        ],
    )

    upsert_page(
        members,
        StandardPage,
        "docs-and-links",
        title="Documents and Links",
        members_only=True,
        intro="Handbooks, forms and the outside references worth bookmarking.",
        body=[
            heading("CalDART documents"),
            rich(
                "<ul>"
                "<li>DART organizing handbook</li>"
                "<li>Exercise planning checklist</li>"
                "<li>Load manifest and weight-and-balance worksheet</li>"
                "<li>Safety policy and volunteer agreement</li>"
                "<li>Bylaws and most recent annual report</li>"
                "</ul>"
                "<p>A website administrator attaches the files to this page as documents; "
                "until then, ask the secretary.</p>"
            ),
            heading("Outside references"),
            rich(
                "<ul>"
                "<li>California Governor's Office of Emergency Services</li>"
                "<li>Air Care Alliance — volunteer pilot organizations</li>"
                "<li>FAA emergency operations and TFR information</li>"
                "<li>Your county's office of emergency services</li>"
                "</ul>"
            ),
        ],
    )
    return members


def seed_settings(site) -> None:
    """Fill in the site settings the example content refers to, without
    overwriting anything an administrator has already changed."""
    from apps.cms.models import SiteSettings

    settings_obj, _ = SiteSettings.objects.get_or_create(site=site)
    defaults = {
        "contact_phone": "(650) 555-0143",
        "mailing_address": "CalDART\nPO Box 1180\nSan Carlos, CA 94070",
        "ein": "47-0000000",
        "donate_url": "/donate/",
        "facebook_url": "https://www.facebook.com/example-caldart",
        "twitter_url": "https://x.com/example_caldart",
    }
    changed = [field for field, value in defaults.items() if not getattr(settings_obj, field)]
    for field in changed:
        setattr(settings_obj, field, defaults[field])
    if changed:
        settings_obj.save(update_fields=changed)


class Command(BaseCommand):
    help = "Create the CalDART example website content (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding site content:")

        seed_darts()
        site = ensure_site_root()
        home = HomePage.objects.get(pk=site.root_page_id)

        about = seed_about(home)
        seed_history(about)
        seed_darts_section(about)
        seed_directors(about)
        seed_news(home)
        seed_join(home)
        seed_donate(home)
        seed_sponsors(home)
        seed_contact(home)
        seed_members_area(home)
        seed_home(home, about_url=about.url or "/about/")
        seed_settings(site)

        grant_website_admin_permissions(stdout=self.stdout)

        from wagtail.models import Page

        total = Page.objects.descendant_of(home, inclusive=True).count()
        self.stdout.write(self.style.SUCCESS(f"Example site ready: {total} pages."))
