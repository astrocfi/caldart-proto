"""The example copy ``manage.py seed_content`` builds the CalDART site from.

Every page is a :class:`PageSpec` holding its slug, title, standfirst and body
blocks; ``seed_content`` reads them and writes the pages.  All of it is *example
content* -- paraphrased from the public CalDART site, not lifted from it -- and
any website administrator can replace it from ``/admin/``.

The copy lives here rather than in the command so that changing a sentence never
touches the code that builds the tree.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from apps.cms.models import MEMBERS_ONLY_COLLECTION_NAME


@dataclass(frozen=True)
class BlockSpec:
    """One block of a page body.

    ``block_type`` is the name the body stream declares, and ``value`` is what that
    block takes: rich text as a string, or the field values of a struct block.
    """

    block_type: str
    value: str | dict[str, str]


@dataclass(frozen=True)
class PageSpec:
    """One page of the example site.

    ``slug`` places it under its parent and ``title`` names it; ``intro`` is the
    standfirst above the body, and ``body`` the blocks below it.  ``show_in_menus``
    puts it in the site navigation, and ``members_only`` puts it behind the
    members-only wall.
    """

    slug: str
    title: str
    intro: str
    body: tuple[BlockSpec, ...] = ()
    show_in_menus: bool = False
    members_only: bool = False


@dataclass(frozen=True)
class NewsPostSpec:
    """One example news post: the page itself, and how many days ago it was posted."""

    page: PageSpec
    days_ago: int


def rich(html: str) -> BlockSpec:
    """A ``paragraph`` body block holding ``html`` as rich text."""
    return BlockSpec("paragraph", html)


def heading(text: str, level: str = "h2") -> BlockSpec:
    """A ``heading`` body block, at H2 unless ``level`` says otherwise."""
    return BlockSpec("heading", {"text": text, "level": level})


def quote(text: str, attribution: str = "") -> BlockSpec:
    """A ``quote`` body block, unattributed unless ``attribution`` is given."""
    return BlockSpec("quote", {"quote": text, "attribution": attribution})


def cta(label: str, url: str, style: str = "primary", note: str = "") -> BlockSpec:
    """A ``cta`` body block: a primary button unless another ``style`` is given."""
    return BlockSpec("cta", {"label": label, "url": url, "style": style, "note": note})


def definition_list(rows: Sequence[tuple[str, str]]) -> str:
    """Rich-text markup for a term/description list, which the blocks allow.

    Each ``(term, text)`` pair becomes one list item with the term in bold and an em
    dash before the text, in the order given; no rows give an empty list.  The
    strings are not escaped, so they are example copy and editor input, never
    anything a visitor supplied.
    """
    items = "".join(f"<li><b>{term}</b> \u2014 {text}</li>" for term, text in rows)
    return f"<ul>{items}</ul>"


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------

HERO_HEADING = "Welcome to CalDART"
HERO_LEDE = "Volunteer pilots, aircraft, and ground crews for California's disasters."
HERO_IMAGE_CAPTION = "Food aid meets the ramp at Reid-Hillview (KRHV). Photo: CalDART."

URGENT_CTA_LABEL = "Request air support"
PRIMARY_CTA_LABEL = "Join CalDART"
PRIMARY_CTA_URL = "/portal/join"
SECONDARY_CTA_LABEL = "Find your DART"

MISSION = (
    "<p>CalDART organizes California pilots and ground personnel to provide volunteer "
    "disaster air transportation services to benefit communities experiencing a major "
    "earthquake, flood, or other disaster.</p>"
)

WELCOME_BODY = (
    "<p>California has some 28,000 aircraft and 54,000 pilots. Most of them would help "
    "after a disaster if they knew how, and CalDART is the way they do: local Disaster "
    "Airlift Response Teams, each based at a general aviation airport, each able to fly "
    "people and supplies between any of the state's roughly 250 public airports under "
    "Part 91 rules.</p>"
    "<p>Every DART runs a practice mobilization exercise at least once a year, and invites "
    "county emergency managers, the local VOAD groups (Volunteer Organizations Active in "
    "Disaster, the nonprofits that coordinate relief work), and neighboring DARTs to take "
    "part. A DART can call for mutual aid from other DARTs, from CalDART members and "
    "friends, and from pilots anywhere in the state.</p>"
)

MISSIONS_HEADING = "Missions flown"

#: What CalDART has carried, newest first: the year, then the mission.
MISSIONS_FLOWN: tuple[tuple[str, str], ...] = (
    (
        "2023",
        "Snowstorms trapped 20,000 people in the San Bernardino Mountains. CalDART used "
        "helicopters to deliver 21,000 lb of medical supplies and food to several "
        "locations.",
    ),
    (
        "2022",
        "A magnitude 6.4 earthquake in Humboldt County brought down power lines, damaged "
        "roads, and cut off towns. CalDART flew emergency supplies to Fortuna for local "
        "volunteers to distribute.",
    ),
    (
        "2021",
        "The Dixie Fire left 200 students without back-to-school supplies. CalDART carried "
        "1,100 lb of them from Chino to Quincy.",
    ),
    (
        "2021",
        "CalDART flew PPE and medical gowns from Santa Barbara to the Yurok Tribe on the "
        "Klamath River.",
    ),
    (
        "2021",
        "Twenty-three aircraft carried 4,800 lb of KN-95 masks, trundle beds, and other "
        "medical supplies from Santa Barbara to firefighters near Eugene, Oregon.",
    ),
    (
        "2020",
        "Face shields from Palo Alto to Walla Walla, Washington, and ventilators from San "
        "Diego to Sacramento.",
    ),
)

TAX_STATUS = (
    "<p>CalDART has no paid employees. Dues and contributions are tax deductible under "
    "IRC 501(c)(3) to the extent allowed by law, and members fly at their own expense as "
    "volunteers.</p>"
)


# ---------------------------------------------------------------------------
# About Us, and the pages below it
# ---------------------------------------------------------------------------

ABOUT = PageSpec(
    slug="about",
    title="About Us",
    show_in_menus=True,
    intro=(
        "CalDART is a statewide network of local Disaster Airlift Response Teams. We recruit, "
        "organize and train general aviation volunteers so California counties have an air "
        "transportation option that does not have to be invented on the day of the disaster."
    ),
    body=(
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
    ),
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

HISTORY = PageSpec(
    slug="history",
    title="History",
    intro=(
        "CalDART grew out of a single Bay Area airport exercise into a statewide network. "
        "These are the milestones that got us here."
    ),
    body=(
        heading("How CalDART began"),
        rich(
            "<p>The idea is older than the organization. Pilots have flown relief loads "
            "after California disasters for decades \u2014 ad hoc, uninsured and usually "
            "unwelcome, because no county emergency manager wants unvetted aircraft "
            "arriving at a damaged airport. The DART model answered that objection: "
            "organize first, train with the agency, and show up with the paperwork "
            "already done.</p>"
        ),
        heading("Milestones"),
        rich(definition_list(HISTORY_MILESTONES)),
        heading("Where we are"),
        rich(
            "<p>Sixteen teams, several hundred members, and a standing invitation to any "
            "California airport that wants to organize one. The bottleneck has never "
            "been aircraft; it is volunteers willing to do the unglamorous organizing "
            "work between disasters.</p>"
        ),
        cta("Join CalDART", "/portal/join", "primary", "Annual membership is $45."),
    ),
)

DART_INDEX = PageSpec(
    slug="darts",
    title="DARTs",
    intro=(
        "Every DART is built around a general aviation airport and led by volunteers who fly "
        "from it. Find the team nearest you, or join as unaffiliated and we will introduce you "
        "to the closest leader."
    ),
    body=(
        heading("Starting a new team"),
        rich(
            "<p>If your airport has no DART, it takes four or five committed volunteers "
            "to start one. Get in touch and a board member will send you the organizing "
            "handbook and introduce you to a nearby leader who has done it.</p>"
        ),
        cta("Contact us", "/contact/", "secondary"),
    ),
)

#: Leader names for the example DART pages -- invented, not real people.
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

#: The domain the example leader contact addresses are built in.
DART_CONTACT_DOMAIN = "caldart.example.org"

#: The summary of a DART that has a home airport.  ``name``, ``where`` and
#: ``county`` are filled in from the team's own record.
DART_SUMMARY = (
    "<p>The {name} DART flies from {where}. Members meet monthly, train "
    "with {county} county emergency services, and take part in "
    "the statewide airlift exercise each year.</p>"
)

#: The summary of the team for members with no DART within reach.
UNAFFILIATED_SUMMARY = (
    "<p>Not every member lives within reach of an organized team. Unaffiliated "
    "members carry a full CalDART membership, receive the same training material "
    "and are called on by the nearest DART when a mission fits.</p>"
)

#: What every DART page carries below its own summary.
DART_PAGE_BODY: tuple[BlockSpec, ...] = (
    heading("Who we need"),
    rich(
        "<ul><li>Pilots with a current certificate and medical</li>"
        "<li>Aircraft owners willing to make an aircraft available</li>"
        "<li>Ground volunteers for manifests, loading and radios</li>"
        "<li>Amateur radio operators</li></ul>"
    ),
    cta("Join this DART", "/portal/join", "primary"),
)

DIRECTORS_ROWS: tuple[tuple[str, str], ...] = (
    (
        "President",
        "Helen Marchetti \u2014 Napa DART, commercial pilot and former county OES planner",
    ),
    ("Vice President", "Samuel Oyelaran \u2014 Hayward DART, CFII and exercise coordinator"),
    ("Secretary", "Teresa Lindqvist \u2014 Santa Rosa DART, aircraft owner and CERT instructor"),
    ("Treasurer", "Marcus Delgado \u2014 Reid-Hillview DART, CPA and private pilot"),
    ("Director at large", "Aiko Tanaka \u2014 Monterey DART, ground team lead"),
    ("Director at large", "Gordon Achebe \u2014 San Carlos DART, ATP and safety officer"),
    ("Director at large", "Rosa Villanueva \u2014 Livermore DART, communications lead"),
)

DIRECTORS = PageSpec(
    slug="directors",
    title="Directors and Officers",
    intro=(
        "CalDART is run by a volunteer board elected by the membership. Directors serve "
        "two-year terms; officers are elected by the board each January."
    ),
    body=(
        heading("Board"),
        rich(definition_list(DIRECTORS_ROWS)),
        heading("Meetings"),
        rich(
            "<p>The board meets by video call on the second Tuesday of each month. "
            "Members are welcome; ask the secretary for the link. Minutes are posted in "
            "the members' area.</p>"
        ),
    ),
)


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

NEWS_INDEX = PageSpec(
    slug="news",
    title="News",
    show_in_menus=True,
    intro="Exercises, new teams, and what the network has been doing.",
)

NEWS_POSTS: tuple[NewsPostSpec, ...] = (
    NewsPostSpec(
        days_ago=12,
        page=PageSpec(
            slug="statewide-exercise-moves-simulated-relief-loads",
            title="Statewide exercise moves simulated relief loads between nine airports",
            intro=(
                "Twenty-eight aircraft and more than sixty ground volunteers took part in this "
                "year's multi-county exercise."
            ),
            body=(
                rich(
                    "<p>Nine DARTs flew a coordinated exercise on Saturday, moving palletized "
                    "\u201crelief supplies\u201d \u2014 in practice, sandbags and marked "
                    "cartons \u2014 between "
                    "airports on a schedule set by a simulated county emergency operations "
                    "center.</p>"
                    "<p>The scenario assumed a magnitude 6.8 earthquake had closed two state "
                    "highways. Ground teams handled manifests, weight and balance checks and "
                    "hand-offs to CERT volunteers at the receiving fields, while amateur radio "
                    "operators passed traffic between the airports and the exercise EOC.</p>"
                    "<p>Debrief notes and the load-planning worksheets are in the members' "
                    "area.</p>"
                ),
                quote(
                    "The point of the exercise is the paperwork and the radios, not the flying. "
                    "The flying is the easy part.",
                    "Exercise coordinator, CalDART",
                ),
            ),
        ),
    ),
    NewsPostSpec(
        days_ago=41,
        page=PageSpec(
            slug="two-new-darts-in-the-central-valley",
            title="Two new teams stand up in the Central Valley",
            intro=(
                "Pilots at two inland airports have completed the organizing checklist and are "
                "recruiting members."
            ),
            body=(
                rich(
                    "<p>Both airports ran their first tabletop exercise with county emergency "
                    "management last month and have started signing up pilots, aircraft owners "
                    "and ground volunteers.</p>"
                    "<p>Standing up a DART takes a core of four or five committed volunteers, a "
                    "conversation with the airport manager and a county contact willing to take "
                    "the call. If that sounds like your field, the organizing handbook is in "
                    "the members' area and a board member will walk you through it.</p>"
                ),
            ),
        ),
    ),
    NewsPostSpec(
        days_ago=96,
        page=PageSpec(
            slug="insurance-and-currency-records-move-online",
            title="Membership, medical and insurance records move online",
            intro=(
                "DART leaders can check a member's currency from a phone on the ramp, "
                "instead of a spreadsheet emailed once a quarter."
            ),
            body=(
                rich(
                    "<p>Members keep their own profile up to date: contact details, certificate "
                    "and medical, the aircraft they commonly fly, and the volunteer roles they "
                    "are willing to take on. Aircraft owners record their liability limits and "
                    "policy expiry once, and every pilot attached to that aircraft benefits.</p>"
                    "<p>Renewal reminders go out at sixty, thirty and seven days. Nobody has to "
                    "chase a lapsed medical by hand any more.</p>"
                ),
            ),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Join, Donate, Sponsors, Contact
# ---------------------------------------------------------------------------

JOIN = PageSpec(
    slug="join",
    title="Join CalDART",
    show_in_menus=True,
    intro=(
        "Membership is open to anyone willing to help \u2014 you do not need to be a pilot, "
        "and you do not need to own an aircraft."
    ),
    body=(
        heading("Dues"),
        rich(
            "<ul>"
            "<li><b>Annual membership \u2014 $45</b>, good for one year from the day it is "
            "paid.</li>"
            "<li><b>Life membership \u2014 $650</b>, paid once, never renewed.</li>"
            "</ul>"
            "<p>Dues are tax deductible. If the fee is a hardship, say so when you apply \u2014 "
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
            "<li><b>Ground volunteers</b> need no certificate at all \u2014 only the "
            "willingness to turn up.</li>"
            "</ul>"
        ),
        heading("What happens next"),
        rich(
            "<p>You create an account, fill in your profile, and pay by card, Apple Pay, "
            "Google Pay or PayPal. Your membership is active the moment the payment "
            "clears \u2014 there is no waiting period and no approval queue. A DART leader "
            "near you will be in touch about the next meeting.</p>"
        ),
        cta(
            "Start your membership",
            "/portal/join",
            "primary",
            "$45 annual or $650 life \u00b7 card, Apple Pay, Google Pay or PayPal",
        ),
    ),
)

CONTRIBUTION_TIERS: tuple[tuple[str, str], ...] = (
    ("$20 \u2014 Participating", "Covers a member's share of exercise materials for a year."),
    ("$100 \u2014 Bronze", "Buys handheld radio batteries and cargo restraint for one team."),
    ("$300 \u2014 Silver", "Funds a tabletop exercise with a county emergency operations center."),
    ("$1,000 \u2014 Gold", "Underwrites a full multi-airport airlift exercise."),
    ("$3,000 \u2014 Diamond", "Equips a new DART with its ground team kit from scratch."),
    ("$10,000 \u2014 Platinum", "Sponsors a season of statewide training and outreach."),
)

DONATE = PageSpec(
    slug="donate",
    title="Donate",
    show_in_menus=True,
    intro=(
        "Dues cover the basics. Contributions pay for the exercises, radios, training material "
        "and insurance that make a DART useful to a county on the worst day of its year."
    ),
    body=(
        heading("Contribution levels"),
        rich(definition_list(CONTRIBUTION_TIERS)),
        rich(
            "<p>Any amount helps, and you can add a contribution to your dues when you "
            "join or renew \u2014 one payment, one receipt.</p>"
        ),
        heading("Other ways to give"),
        rich(
            "<ul>"
            "<li><b>Employer matching</b> \u2014 many California employers match charitable "
            "gifts. Ask us for our EIN and determination letter.</li>"
            "<li><b>In kind</b> \u2014 fuel, hangar space, radios, cargo restraint and "
            "avionics work are all as useful as cash.</li>"
            "<li><b>Sponsorship</b> \u2014 businesses that support a season of training are "
            "listed on our sponsors page.</li>"
            "</ul>"
        ),
        cta("Give with your renewal", "/portal/renew", "secondary"),
    ),
)

SPONSOR_ROWS: tuple[tuple[str, str], ...] = (
    (
        "Bay Meridian Aviation",
        "Fixed-base operator \u2014 donated ramp space and fuel for exercises.",
    ),
    (
        "Sierra Avionics Works",
        "Avionics shop \u2014 discounted ADS-B and radio installations for members.",
    ),
    (
        "Golden Poppy Flying Club",
        "Flying club \u2014 aircraft made available for training weekends.",
    ),
    ("Coast Range Insurance Brokers", "Broker \u2014 guidance on volunteer liability cover."),
    ("Delta Fuel & Line Service", "Line service \u2014 fuel discounts on exercise days."),
)

SPONSORS = PageSpec(
    slug="sponsors",
    title="Sponsors",
    intro=(
        "CalDART's work is supported by flying clubs, fixed-base operators, avionics shops and "
        "businesses across California. Sponsors are listed here with their permission; nothing "
        "on this page is a paid endorsement."
    ),
    body=(
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
    ),
)

CONTACT = PageSpec(
    slug="contact",
    title="Contact Us",
    show_in_menus=True,
    intro=(
        "<p>The fastest way to reach us is email. Messages go to the board and are usually "
        "answered within a few days by a volunteer \u2014 please be patient, nobody here is "
        "paid.</p>"
        "<p>If you want to join a specific team, say which airport you fly from and we will put "
        "you in touch with that DART's leader directly.</p>"
    ),
    body=(
        heading("Media inquiries"),
        rich(
            "<p>Please email rather than calling. A board member will respond, and we "
            "will happily put you in touch with a DART leader in your area.</p>"
        ),
        heading("Already a member?"),
        rich(
            "<p>Membership questions \u2014 renewals, receipts, a change of address \u2014 are "
            "fastest through the member portal.</p>"
        ),
        cta("Open the member portal", "/portal/", "quiet"),
    ),
)


# ---------------------------------------------------------------------------
# The members area
# ---------------------------------------------------------------------------

MEMBERS = PageSpec(
    slug="members",
    title="Members",
    show_in_menus=True,
    members_only=True,
    intro=(
        "Handbooks, exercise material, forms and the current roster. This area is open to "
        "members with a current membership, and to DART leaders and administrators."
    ),
    body=(
        heading("What is in here"),
        rich(
            "<ul>"
            "<li>The DART organizing handbook and exercise playbooks</li>"
            "<li>Load planning worksheets and manifest forms</li>"
            "<li>Board minutes and the annual report</li>"
            "<li>The current roster and DART leader contact list</li>"
            "</ul>"
        ),
    ),
)

MEMBERS_ONLY = PageSpec(
    slug="members-only",
    title="Members Only",
    members_only=True,
    intro="Notices for current members, posted by the board and by DART leaders.",
    body=(
        heading("Next statewide exercise"),
        rich(
            "<p>Briefing packets go out four weeks ahead. Tell your DART leader whether "
            "you are flying, crewing on the ground or unavailable, so the load plan can "
            "be built against real aircraft.</p>"
        ),
        heading("Keep your record current"),
        rich(
            "<p>Check your medical and flight review dates in the portal, and \u2014 if you "
            "own the aircraft you fly \u2014 your insurance expiry. A DART leader checks "
            "these before dispatching you, and a lapsed date is the most common reason a "
            "willing member sits out a mission.</p>"
        ),
        cta("Check my profile", "/portal/profile", "secondary"),
    ),
)

DOCS_AND_LINKS = PageSpec(
    slug="docs-and-links",
    title="Documents and Links",
    members_only=True,
    intro="Handbooks, forms and the outside references worth bookmarking.",
    body=(
        heading("CalDART documents"),
        rich(
            "<ul>"
            "<li>DART organizing handbook</li>"
            "<li>Exercise planning checklist</li>"
            "<li>Load manifest and weight-and-balance worksheet</li>"
            "<li>Safety policy and volunteer agreement</li>"
            "<li>Bylaws and most recent annual report</li>"
            "</ul>"
            "<p>A website administrator uploads each file into the "
            f"<strong>{MEMBERS_ONLY_COLLECTION_NAME}</strong> document collection and "
            "links it from this page; a document in that collection is served only to "
            "the people who can read this page. Until the files are up, ask the "
            "secretary.</p>"
        ),
        heading("Outside references"),
        rich(
            "<ul>"
            "<li>California Governor's Office of Emergency Services</li>"
            "<li>Air Care Alliance \u2014 volunteer pilot organizations</li>"
            "<li>FAA emergency operations and TFR information</li>"
            "<li>Your county's office of emergency services</li>"
            "</ul>"
        ),
    ),
)


# ---------------------------------------------------------------------------
# Site settings
# ---------------------------------------------------------------------------

#: The settings the example content refers to, written only where the field is
#: still empty so an administrator's own value survives a re-seed.
SITE_SETTINGS: dict[str, str] = {
    "duty_phone": "(408) 713-0646",
    "duty_phone_note": "Answered by the CalDART member on watch",
    "mailing_address": "CalDART\nPO Box 606\nSan Martin, CA 95046",
    "ein": "83-1407209",
    "donate_url": "/donate/",
    "facebook_url": "https://www.facebook.com/example-caldart",
    "twitter_url": "https://x.com/example_caldart",
}
