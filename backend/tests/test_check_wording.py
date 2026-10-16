"""``scripts/check_wording.py``, the wording check ``make lint-wording`` runs.

The check flags a verb whose object is a negative (``no``, ``nothing``, ``nobody``,
``none``, ``no one``, ``nobody's``, or ``no one's``), the wording the project's prose
rule forbids, and fails on any hit.  Each flagged example below ends
its line with the ignore marker, so the check passes over this file itself.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_wording.py"
WORDS = REPO_ROOT / "scripts" / "wording_words.py"
MAKEFILE = REPO_ROOT / "Makefile"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: The resolved ``git``, or ``None`` on a machine without one.
GIT = shutil.which("git")

#: The same-line marker, split so that this line itself is still checked.
MARKER = "wording" + ":ignore"

#: The page every ``tree`` starts with, which doesn't hold a hit.
CLEAN_PAGE = "No token found.\nIt doesn't send anything.\n"

#: A page with two hits.
PAGE = "It has no token.\nIt took none.\n"  # wording:ignore

#: The opening and closing typographic single quotes, kept out of this file's source.
OPEN_QUOTE, CLOSE_QUOTE = chr(0x2018), chr(0x2019)


def _load(name: str, source: Path) -> ModuleType:
    """Import ``source`` as ``name`` from its path, since ``scripts`` isn't a package.

    The module is registered in ``sys.modules`` first, as a normal import would, so its
    dataclasses can resolve their own module and a later import of ``name`` finds it.
    """
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# The check imports its word lists as ``wording_words``, and its text primitives and its
# relative-clause check as ``wording_text`` and ``wording_relative``, the names a run from
# ``scripts/`` gives them, so they load under those names first, in import order.
word_lists = _load("wording_words", WORDS)
_load("wording_text", REPO_ROOT / "scripts" / "wording_text.py")
_load("wording_relative", REPO_ROOT / "scripts" / "wording_relative.py")
checker = _load("caldart_check_wording", SCRIPT)


def _hit_count(text: str) -> int:
    """How many hits the check finds in ``text``, read as a file named ``page.rst``."""
    return len(checker.find_hits(text, "page.rst"))


# -- what is flagged -------------------------------------------------------------

FLAGGED = {
    "has-no": "A donor has no portal account.",  # wording:ignore
    "holds-no": "The dashboard holds no charge.",  # wording:ignore
    "took-nothing": "It took nothing.",  # wording:ignore
    "charges-nobody": "The run charges nobody.",  # wording:ignore
    "sends-nothing": "The form sends nothing.",  # wording:ignore
    "offers-none": "The plan offers none.",  # wording:ignore
    "changes-nothing": "The request changes nothing.",  # wording:ignore
    "does-nothing": "The link does nothing.",  # wording:ignore
    "did-nothing": "Clicking it did nothing.",  # wording:ignore
    "do-nothing": "Then do nothing.",  # wording:ignore
    "found-no-one": "The scan found no one to charge.",  # wording:ignore
    "upper-case": "A Member HAS NO term.",  # wording:ignore
    "participle-after-has": "The renewal has sent nothing.",  # wording:ignore
    "after-a-hyphen": "The scan re-sends nothing.",  # wording:ignore
    "pronoun-between": "Renewing now costs you nothing.",  # wording:ignore
    "it-between": "The scan sends it no more charges.",  # wording:ignore
    "adverb-between": "The page has almost no room.",  # wording:ignore
    "notifies-nobody": "The change notifies nobody.",  # wording:ignore
    "rejects-none": "The import rejects none.",  # wording:ignore
    "tested-nothing": "The run tested nothing.",  # wording:ignore
    "unlisted-past-tense": "The job frobnicated nothing.",  # wording:ignore
    "no-more": "It sends no more charges.",  # wording:ignore
    "there-is-no": "There is no payment.",  # wording:ignore
    "there-are-no": "There are no releases.",  # wording:ignore
    "there-was-none": "A result appears where there was none.",  # wording:ignore
    "is-no": "A tombstone is no account.",  # wording:ignore
    "are-no": "The reminders are no help.",  # wording:ignore
    "was-no": "It was no surprise.",  # wording:ignore
    "be-no": "It will be no trouble.",  # wording:ignore
    "is-deliberately-no": "There is deliberately no restore endpoint.",  # wording:ignore
    "with-no": "A member with no term is a friend.",  # wording:ignore
    "for-no-one": "It is for no one in particular.",  # wording:ignore
    "for-no-reason": "It failed for no reason.",  # wording:ignore
    "of-no": "A gift of no value.",  # wording:ignore
    "at-no-cost": "It is checked at no cost.",  # wording:ignore
    "in-no-case": "In no case is the card charged twice.",  # wording:ignore
    "in-no-list": "A donor appears in no member list.",  # wording:ignore
    "as-no": "It is stored as no account.",  # wording:ignore
    "to-nothing": "A name that normalizes to nothing is refused.",  # wording:ignore
    "remains-nothing": "Once settled, there remains nothing to charge.",  # wording:ignore
    "after-an-opening-quote": "it('offers no reset', () => {",  # wording:ignore
    "before-a-closing-quote": "it('says leaving changes nothing')",  # wording:ignore
    "after-docstring-quotes": '"""Has no term."""',  # wording:ignore
    "typographic-quotes": f"It reads {OPEN_QUOTE}sends nothing{CLOSE_QUOTE}.",  # wording:ignore
    "nobody-s": "It changes nobody's role.",  # wording:ignore
    "no-one-s": "It sets no one's password.",  # wording:ignore
    "nobody-s-typographic": f"It changes nobody{CLOSE_QUOTE}s role.",  # wording:ignore
    "nobody-s-wrapped": "It changes\nnobody's role.",  # wording:ignore
    "nobody-s-before-an-ing-noun": "It changes nobody's billing address.",  # wording:ignore
    "nobody-s-before-an-ed-noun": "It keeps nobody's saved filters.",  # wording:ignore
    "split-literal": '"so there is " "no server"',  # wording:ignore
    "split-literal-space-after": '"so there is" " no server"',  # wording:ignore
    "split-literal-plus": "'it has ' + 'nothing'",  # wording:ignore
    "split-literal-line-break": '"so there is "\n    "no server"',  # wording:ignore
    "split-literal-plus-line-break": '"so there is " +\n    "no server"',  # wording:ignore
    "bold-negative": "It sets **no** security headers.",  # wording:ignore
    "bold-phrase": "It **has no** default.",  # wording:ignore
    "italic-negative": "A user with *no* roles.",  # wording:ignore
    "strong-tag": "<strong>has no</strong> term",  # wording:ignore
    "b-tag": "It has <b>no</b> term.",  # wording:ignore
    "em-tag": "It sends <em>nothing</em>.",  # wording:ignore
    "i-tag": "It sends <i>nothing</i>.",  # wording:ignore
    "there-s": "There's no payment.",  # wording:ignore
    "it-s": "It's no help.",  # wording:ignore
    "that-s": "That's none of it.",  # wording:ignore
    "we-re": "We're no help.",  # wording:ignore
    "you-ve": "You've no account.",  # wording:ignore
    "they-d": "They'd no term.",  # wording:ignore
    "typographic-contraction": f"There{CLOSE_QUOTE}s no payment.",  # wording:ignore
    "nobody-before-a-plural-noun": "It sends nobody emails.",  # wording:ignore
    "no-one-before-a-plural-noun": "It gives no one refunds.",  # wording:ignore
    "capitalized-title": "Members with No Term",  # wording:ignore
    "capitalized-after-a-lower-case-verb": "It has No Account.",  # wording:ignore
}


@pytest.mark.parametrize("text", list(FLAGGED.values()), ids=list(FLAGGED))
def test_a_verb_with_a_negative_object_is_flagged(text: str) -> None:
    """Each phrase puts the negation on a verb's object, so it is one hit."""
    assert _hit_count(text) == 1


#: Irregular pasts and past participles, each of which can stand before a negative.
PARTICIPLES = (
    "given", "sent", "found", "shown", "taken", "written", "kept", "held", "told", "paid",
    "made", "done", "left", "put", "set", "read", "mailed", "charged",
)  # fmt: skip

#: Where a participle stands: after a form of "be", after "has", or after another verb.
PARTICIPLE_FRAMES = {
    "after-is": "The member is {} nothing.",
    "after-was": "The member was {} none.",
    "after-has": "The member has {} nothing.",
    "after-gets": "The member gets {} nothing.",
    "after-a-noun": "The run {} nobody.",
}


@pytest.mark.parametrize("form", PARTICIPLES)
@pytest.mark.parametrize("frame", list(PARTICIPLE_FRAMES.values()), ids=list(PARTICIPLE_FRAMES))
def test_a_participle_before_a_negative_is_flagged(form: str, frame: str) -> None:
    """A past or a participle before a negative ("is sent", "gets paid") is one hit."""
    assert _hit_count(frame.format(form)) == 1


ALLOWED = {
    "no-payment-found": "No payment found.",
    "nobody-as-subject": "Nobody changes their own roles.",
    "nothing-as-subject": "Nothing is due.",
    "subject-after-so": "A donor cannot sign in, so no reset email was sent.",
    "subject-after-when": "It answers 204 when nobody was signed in.",
    "no-longer": "The link may no longer work.",
    "is-no-longer": "The link is no longer valid.",
    "no-matter": "It runs no matter what.",
    "python-none": "It returns None when the row is missing.",
    "than-nothing": "More than nothing but less than the minimum.",
    "or-no": "A yes or no answer.",
    "no-deeper": "Tags must nest no deeper than three.",
    "said-no-full-stop": "The member said no.",
    "says-no-comma": "If the member says no, nothing is sent.",
    "all-caps-constant": "It returns NONE when the key is unset.",
    "table-padding": "joined_on   Joined      no      Start",
    "preposition-then-pronoun": "Pass --yes; without it nothing runs.",
    "pronoun-then-a-clause": "Tell them nobody is coming.",
    "pronoun-then-a-modal": "Tell them nobody can sign in.",
    "indeed-no": "Indeed no payment was found.",
    "noun-object-known-gap": "It sends a donor nothing.",
    "determiner-before-a-verb-form": "A change is made, so nobody is signed in.",
    "clause-after-a-verb": "It says nothing is hidden.",
    "clause-past-else": "It says nothing else needs fixing.",
    "clause-with-has": "It says nothing has gone yet.",
    "clause-with-a-modal": "It says no one can sign in.",
    "clause-with-a-present-verb": "It shows that nobody matches.",
    "inverted-question": "Has nothing been sent?",
    "quoted-label": "The row reads No insurance on file.",
    "quoted-message": "The page says Nothing to charge.",
    "nobody-s-as-a-subject": "Nobody's role changes.",
    "nobody-s-before-a-participle": "It says nobody's signed in.",
    "nobody-s-before-here": "It says nobody's here.",
    "nobody-s-before-been": "It says nobody's been charged.",
    "no-one-s-before-an-ing-form": "It says no one's going.",
    "nobody-s-before-a-base-form-participle": "It says nobody's set up yet.",
    "nobody-s-before-an-ed-word-and-an-adverb": "It says nobody's charged twice.",
    "nobody-s-before-an-irregular-participle": "It says nobody's given consent.",
    "nobody-s-at-the-end": "It says nobody's signed.",
    "nothing-before-a-present-verb": "It says nothing changes.",
    "none-before-a-present-verb": "It says none applies.",
    "nobody-before-a-modal": "It says nobody can.",
    "no-one-before-have": "It says no one have.",
    "nobody-before-had": "It says nobody had.",
    "quoted-message-at-the-end": "The page says No.",
    "contraction-before-no-longer": "It's no longer due.",
    "split-literal-without-a-space": '"is" "no"',
    "emphasis-before-a-subject": "It says **nothing** is hidden.",
}


@pytest.mark.parametrize("text", list(ALLOWED.values()), ids=list(ALLOWED))
def test_wording_the_rule_allows_is_not_flagged(text: str) -> None:
    """A negative subject, an idiom after ``no``, an answer, a value, or a noun is passed.

    A negative subject includes one that opens a clause after a verb ("says nothing is
    hidden") and ``nobody's`` meaning "nobody is"; a capitalized negative after a
    lower-case verb is a quoted label.  ``noun-object-known-gap`` is a gap the check
    documents: a noun between the verb and the negative puts the verb out of reach.
    """
    assert _hit_count(text) == 0


IDENTIFIERS = {
    "snake-case": "def has_no_term(member):",
    "camel-case": "const hasNoTerm = true;",
    "snake-case-nothing": "holds_nothing = False",
    "is-none": "if value is None:",
    "flag": "send --no-input",
    "hyphen": "Cache-Control: has no-store",
    "quoted": "takes 'none' as its value",
    "hyphenated-after-a-possessive": "the member's no-show",
    "inline-literal": "It takes ``none`` as its value.",
    "inline-literal-after-is": "The default is ``none``.",
    "list-of-literals": '["has", "no"]',
}


@pytest.mark.parametrize("text", list(IDENTIFIERS.values()), ids=list(IDENTIFIERS))
def test_an_identifier_or_a_quoted_value_never_matches(text: str) -> None:
    """Only whitespace-separated words count, so code identifiers stay out."""
    assert _hit_count(text) == 0


def test_a_phrase_wrapped_across_two_lines_is_flagged_on_the_verb_line() -> None:
    """A docstring that breaks between the verb and the negative is still one hit."""
    hits = checker.find_hits("First line.\nThe donor has\n    no account.\n", "page.rst")
    assert [hit.line for hit in hits] == [2]


def test_a_phrase_wrapped_across_two_comment_lines_is_flagged() -> None:
    """The continuation's comment leader counts as whitespace between the two words."""
    assert _hit_count("# The check holds\n# nothing back.\n") == 1


def test_the_hit_carries_its_path() -> None:
    """A hit names the file it was found in."""
    hit = checker.find_hits("The run charges nobody.\n", "docs/x.rst")[0]  # wording:ignore
    assert hit.path == "docs/x.rst"


def test_the_hit_carries_the_text_of_its_line_stripped() -> None:
    """A hit carries its line's text without the surrounding whitespace."""
    hit = checker.find_hits("  The run charges nobody.\n", "docs/x.rst")[0]  # wording:ignore
    assert hit.text == "The run charges nobody."  # wording:ignore


def test_the_flagged_and_allowed_words_are_disjoint() -> None:
    """No word is both flagged and deliberately allowed."""
    assert checker.FLAGGED_FORMS.isdisjoint(checker.ALLOWED_FORMS)


def test_no_allowed_word_is_listed_twice() -> None:
    """Each allowed word is written down once."""
    words = [word for group in word_lists.ALLOWED_WORDS for word in group.split()]
    assert len(words) == len(set(words))


def test_no_flagged_word_is_listed_twice() -> None:
    """Each word in ``FLAGGED_WORDS`` is written down once."""
    words = [word for group in checker.FLAGGED_WORDS for word in group.split()]
    assert len(words) == len(set(words))


def test_every_verb_family_has_five_forms() -> None:
    """Base, third person, past, past participle, and present participle, in order."""
    assert {len(family.split()) for family in checker.FLAGGED_VERBS} == {5}


def test_no_verb_form_belongs_to_two_families() -> None:
    """Each flagged form appears in one family, so its suggestion is unambiguous."""
    forms = [form for family in checker.FLAGGED_VERBS for form in set(family.split())]
    assert len(forms) == len(set(forms))


# -- negative relative clauses ---------------------------------------------------

RELATIVE_CLAUSES = {
    "nobody-has": "It refuses a fee nobody has reported yet.",  # wording:ignore
    "no-noun-can": "Refuse a day no statement can have carried yet.",  # wording:ignore
    "no-noun-has": "Answers 404 for an id no row has.",  # wording:ignore
    "nobody-is": "It asks before deleting a DART nobody is on.",  # wording:ignore
    "nothing-is": "It reads a query nothing is watching.",  # wording:ignore
    "nobody-can": "Save never sends back a filter nobody can see.",  # wording:ignore
    "no-one-has": "It skips a form no one has typed in.",  # wording:ignore
    "adjective-before-the-noun": "It keeps a deleted member nobody can restore.",  # wording:ignore
    "bare-past": "A claim nobody finished is taken to have died.",  # wording:ignore
    "bare-present": "An address nobody reads is skipped.",  # wording:ignore
    "unlisted-present": "It drops the module nothing exercises.",  # wording:ignore
    "two-word-subject": "It refuses a slug no active plan carries.",  # wording:ignore
    "plural-subject-base-verb": "It drops a key no columns carry.",  # wording:ignore
    "plural-noun": "The records nobody edited stay.",  # wording:ignore
    "verb-form-as-noun": "A change nobody is signed in for.",  # wording:ignore
    "past-participle": "A field nobody has filled in is blank.",  # wording:ignore
    "else": "An address nobody else holds is counted.",  # wording:ignore
    "adverb": "It picks a contrast no reader ever sees.",  # wording:ignore
    "capitalized-noun": "It keeps a Stripe SetupIntent nobody will confirm.",  # wording:ignore
    "hyphenated-adjective": "A two-component fixture no serializer produces.",  # wording:ignore
    "whose": "It names one whose fee nobody has reported.",  # wording:ignore
    "inside-a-phrase": "It counts a payment for a caller nobody has signed in.",  # wording:ignore
    "wrapped": "It counts a caller nobody\n    has signed in.",  # wording:ignore
    "comment-wrapped": "# It counts a caller\n# nobody has signed in.",  # wording:ignore
    "test-name": "it('asks before deleting a DART nobody is on', () => {",  # wording:ignore
    "after-a-literal": "Returns ``None`` for a change nobody is signed in for.",  # wording:ignore
    "after-a-bracket": "It counts (by address) a caller nobody has signed in.",  # wording:ignore
    "two-determiners": "It is the one cell no row fills.",  # wording:ignore
    "after-a-comma": "Not Insured, for a policy nobody has checked.",  # wording:ignore
    "hyphenated-subject": "Null for a change no signed-in account made.",  # wording:ignore
    "irregular-past": "It raises a fault nobody foresaw.",  # wording:ignore
}


@pytest.mark.parametrize("text", list(RELATIVE_CLAUSES.values()), ids=list(RELATIVE_CLAUSES))
def test_a_negative_relative_clause_after_a_noun_is_flagged(text: str) -> None:
    """A noun followed by a negative subject and its verb is one hit."""
    assert _hit_count(text) == 1


NOT_RELATIVE_CLAUSES = {
    "preposition-lead-in": "On any failure nothing is written.",
    "preposition-lead-in-after-a-sentence": "It ends.  On any failure nothing is written.",
    "preposition-lead-in-after-quotes": '"""Without a token nothing was sent."""',
    "preposition-lead-in-after-a-conjunction": "It stops, and on a failure nothing is kept.",
    "preposition-lead-in-after-a-semicolon": "It stops; in that case nothing is kept.",
    "comma-before-the-subject": "After the run, nothing is sent.",
    "colon-before-the-subject": "One rule holds for the run: nothing is sent twice.",
    "conjunction-before-the-subject": "The filters stay when nothing matches.",
    "and-before-the-subject": "It skips the restore and no job runs.",
    "but-before-the-subject": "It has a name but no file of its own.",
    "no-longer": "The link no longer works.",
    "no-matter": "A charge no matter how small is logged.",
    "no-wider": "It holds a panel no wider than the page.",
    "verb-after-a-noun-subject": "The page says nothing is hidden.",
    "past-tense-after-a-noun-subject": "The scan said nothing was due.",
    "participle-before-the-subject": "Once the job is done nothing runs.",
    "none-of": "It reads the rows none of which match.",
    "quoted-label": "The row reads No insurance on file.",
    "python-none": "The default None is used.",
    "all-caps-constant": "The value NONE is used.",
}


@pytest.mark.parametrize(
    "text", list(NOT_RELATIVE_CLAUSES.values()), ids=list(NOT_RELATIVE_CLAUSES)
)
def test_a_negative_that_starts_a_clause_of_its_own_is_not_flagged(text: str) -> None:
    """A negative after punctuation, a conjunction, or a lead-in phrase is a subject.

    So is one after a verb, an idiom after ``no``, a quoted label, and a value.
    """
    assert _hit_count(text) == 0


def test_a_relative_clause_carries_its_suggestion() -> None:
    """The hit names the phrase and points at an adjective or a positive clause."""
    text = "It refuses a fee nobody has reported."  # wording:ignore
    hit = checker.find_hits(text, "page.rst")[0]
    assert hit.suggestion == (
        "a fee nobody has -> rewrite as an adjective or 'that doesn't ...'"  # wording:ignore
    )


def test_a_relative_clause_is_flagged_on_its_determiner_line() -> None:
    """A clause wrapped after the noun is reported on the line its noun phrase starts."""
    hits = checker.find_hits("First line.\nIt counts a caller\nnobody has signed in.\n", "x")
    assert [hit.line for hit in hits] == [2]


def test_a_relative_clause_on_a_marked_line_is_not_flagged() -> None:
    """The ignore marker keeps a relative clause verbatim too."""
    assert _hit_count(f"Refuse an id no row has.  # {MARKER}\n") == 0  # wording:ignore


def test_hits_of_both_kinds_come_in_order() -> None:
    """A relative clause and a negative object are listed by line."""
    text = "It took none.\nAn id no row has.\nIt has no term.\n"  # wording:ignore
    assert [hit.line for hit in checker.find_hits(text, "page.rst")] == [1, 2, 3]


# -- the ignore markers ----------------------------------------------------------


def test_the_ignore_marker_on_the_same_line_silences_it() -> None:
    """The marker anywhere on the line keeps the phrase verbatim."""
    assert _hit_count(f"The API has no token.  # {MARKER}\n") == 0  # wording:ignore


def test_the_ignore_marker_on_either_line_of_a_wrapped_phrase_silences_it() -> None:
    """The continuation line can carry the marker too."""
    assert _hit_count(f"The API has\nno token.  # {MARKER}\n") == 0  # wording:ignore


def test_the_next_line_marker_silences_the_following_line() -> None:
    """The next-line marker keeps the next line, where a trailing comment cannot go."""
    text = f"<!-- {MARKER}-next-line -->\nThe API has no token.\n"  # wording:ignore
    assert _hit_count(text) == 0


def test_an_rst_marker_comment_covers_the_whole_next_paragraph() -> None:
    """A ``..`` comment holding only the next-line marker covers the next paragraph.

    It skips the blank line after the comment and covers every line through the next
    blank one; the paragraph after that is checked.
    """
    text = (
        f".. {MARKER}-next-line\n\n"
        "It has no token and\nit took nothing.\n\n"  # wording:ignore
        "It sends nothing.\n"  # wording:ignore
    )
    assert [hit.line for hit in checker.find_hits(text, "page.rst")] == [6]


def test_the_next_line_marker_leaves_its_own_line_flagged() -> None:
    """The next-line marker doesn't silence its own line."""
    text = f"It has no token. <!-- {MARKER}-next-line -->\n\n"  # wording:ignore
    assert _hit_count(text) == 1


# -- suggestions -----------------------------------------------------------------

SUGGESTIONS = {
    "a": ("It has no portal.", "has no portal -> doesn't have a portal"),  # wording:ignore
    "an": ("It has no address.", "has no address -> doesn't have an address"),  # wording:ignore
    "any-plural": ("It has no terms.", "has no terms -> doesn't have any terms"),  # wording:ignore
    "anything": ("It sends nothing.", "sends nothing -> doesn't send anything"),  # wording:ignore
    "past": ("It took nothing.", "took nothing -> didn't take anything"),  # wording:ignore
    "anybody": ("It charges nobody.", "charges nobody -> doesn't charge anybody"),  # wording:ignore
    "anyone": ("It found no one.", "found no one -> didn't find anyone"),  # wording:ignore
    "any": ("It offers none.", "offers none -> doesn't offer any"),  # wording:ignore
    "do": ("It does nothing.", "does nothing -> doesn't do anything"),  # wording:ignore
    "after-has": ("It has sent none.", "has sent none -> hasn't sent any"),  # wording:ignore
    "capital": ("Has no fee.", "Has no fee -> Doesn't have a fee"),  # wording:ignore
    "pronoun": ("It costs you none.", "costs you none -> doesn't cost you any"),  # wording:ignore
    "at-most": ("It has no more than 255.", "has no more than -> has at most"),  # wording:ignore
    "at-least": ("It has no fewer than 2.", "has no fewer than -> has at least"),  # wording:ignore
    "less-than": ("It is no less than 5.", "is no less than -> is at least"),  # wording:ignore
    "is": ("There is no payment.", "is no payment -> isn't a payment"),  # wording:ignore
    "are": ("There are no rows.", "are no rows -> aren't any rows"),  # wording:ignore
    "was": ("There was none.", "was none -> wasn't any"),  # wording:ignore
    "with": ("A member with no term.", "with no term -> without a term"),  # wording:ignore
    "with-nobody": ("Run with nobody.", "with nobody -> without anybody"),  # wording:ignore
    "after-is": ("It is sent nothing.", "is sent nothing -> isn't sent anything"),  # wording:ignore
    "after-was": (
        "He was given no reason.",  # wording:ignore
        "was given no reason -> wasn't given a reason",  # wording:ignore
    ),
    "after-gets": (
        "It gets paid none.",  # wording:ignore
        "gets paid none -> doesn't get paid any",  # wording:ignore
    ),
    "after-got": (
        "It got told nothing.",  # wording:ignore
        "got told nothing -> didn't get told anything",  # wording:ignore
    ),
    "nobody-s": (
        "It changes nobody's role.",  # wording:ignore
        "changes nobody's role -> doesn't change anybody's role",  # wording:ignore
    ),
    "no-one-s": (
        "It sets no one's password.",  # wording:ignore
        "sets no one's password -> doesn't set anyone's password",  # wording:ignore
    ),
    "opening-quote": (
        "it('offers no reset')",  # wording:ignore
        "offers no reset -> doesn't offer a reset",  # wording:ignore
    ),
    "there-s": (
        "There's no payment.",  # wording:ignore
        "There's no payment -> There isn't a payment",  # wording:ignore
    ),
    "we-re": ("We're none.", "We're none -> We aren't any"),  # wording:ignore
    "you-ve": (
        "You've no idea.",  # wording:ignore
        "You've no idea -> You don't have an idea",  # wording:ignore
    ),
    "they-d": ("They'd none.", "They'd none -> They didn't have any"),  # wording:ignore
    "participle-after-it-s": (
        "It's sent nothing.",  # wording:ignore
        "It's sent nothing -> It isn't sent anything",  # wording:ignore
    ),
    "participle-after-they-d": (
        "They'd sent nothing.",  # wording:ignore
        "They'd sent nothing -> They hadn't sent anything",  # wording:ignore
    ),
    "participle-after-we-ve": (
        "We've sent none.",  # wording:ignore
        "We've sent none -> We haven't sent any",  # wording:ignore
    ),
    "split-literal": (
        '"so there is " "no server"',  # wording:ignore
        "is no server -> isn't a server",  # wording:ignore
    ),
    "bold": (
        "It sets **no** headers.",  # wording:ignore
        "sets no headers -> doesn't set any headers",  # wording:ignore
    ),
}


@pytest.mark.parametrize(("text", "suggestion"), list(SUGGESTIONS.values()), ids=list(SUGGESTIONS))
def test_a_simple_verb_carries_a_suggested_rewrite(text: str, suggestion: str) -> None:
    """A present or simple-past verb gets the rewrite with the negation on the verb."""
    assert checker.find_hits(text, "page.rst")[0].suggestion == suggestion


def test_a_phrase_with_a_degree_adverb_has_a_suggestion_of_none() -> None:
    """An adverb before the negative leaves the rewrite open, so it offers ``None``."""
    hit = checker.find_hits("It has almost no room.", "page.rst")[0]  # wording:ignore
    assert hit.suggestion is None


def test_a_preposition_other_than_with_has_a_suggestion_of_none() -> None:
    """A preposition other than ``with`` moves the negation to the verb: ``None``."""
    hit = checker.find_hits("It failed for no reason.", "page.rst")[0]  # wording:ignore
    assert hit.suggestion is None


def test_a_participle_after_been_has_a_suggestion_of_none() -> None:
    """``has been sent`` takes its negative on ``has``, out of reach: ``None``."""
    hit = checker.find_hits("It has been sent nothing.", "page.rst")[0]  # wording:ignore
    assert hit.suggestion is None


def test_a_base_form_has_a_suggestion_of_none() -> None:
    """An infinitive such as ``to change`` followed by a negative gets ``None``."""
    hit = checker.find_hits("Asked to change nothing.", "page.rst")[0]  # wording:ignore
    assert hit.suggestion is None


# -- the command line ------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    """Write ``text`` to ``path``, creating its directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A throwaway git checkout with one scanned page that doesn't hold a hit."""
    if GIT is None:
        pytest.skip("git is not installed")
    subprocess.run(  # noqa: S603 - fixed argv, GIT is a resolved path
        [GIT, "init", "-q", str(tmp_path)], check=True
    )
    _write(tmp_path / "docs" / "page.rst", CLEAN_PAGE)
    _track(tmp_path)
    return tmp_path


def _track(root: Path) -> None:
    """Stage every file under ``root``, so git tracks it."""
    assert GIT is not None
    subprocess.run(  # noqa: S603 - fixed argv, GIT is a resolved path
        [GIT, "add", "-A"], cwd=root, check=True
    )


def test_a_clean_tree_passes(tree: Path) -> None:
    """A tree without a hit exits 0."""
    assert checker.main([], root=tree) == 0


def test_a_clean_tree_says_it_passed(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The pass prints one line."""
    checker.main([], root=tree)
    assert capsys.readouterr().out == "Wording check passed.\n"


def test_any_hit_fails(tree: Path) -> None:
    """One hit anywhere in the tree exits 1."""
    _write(tree / "frontend" / "src" / "Page.tsx", "<p>It holds no charge.</p>\n")  # wording:ignore
    assert checker.main([], root=tree) == 1


def test_each_hit_prints_with_its_suggestion(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The failure names the line and suggests the rewrite."""
    _write(tree / "docs" / "page.rst", PAGE)
    checker.main([], root=tree)
    expected = (
        "docs/page.rst:2: It took none.\n    took none -> didn't take any\n"  # wording:ignore
    )
    assert expected in capsys.readouterr().out


def test_the_failure_ends_with_the_total_and_the_remedy(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The last line counts the hits and files and names the ignore marker."""
    _write(tree / "docs" / "page.rst", PAGE)
    checker.main([], root=tree)
    last = capsys.readouterr().out.splitlines()[-1]
    assert last == (
        "2 hits in 1 file.  Put the negation on the verb, or rewrite a negative relative "
        "clause, as each suggestion shows, or end a line that must stay verbatim with a "
        f"{MARKER} comment."
    )


def test_an_untracked_file_is_checked(tree: Path) -> None:
    """A file git doesn't track yet, and ``.gitignore`` doesn't exclude, is checked."""
    _write(tree / "backend" / "a.py", '"""It took none."""\n')  # wording:ignore
    assert checker.main([], root=tree) == 1


def test_a_gitignored_file_is_never_checked(tree: Path) -> None:
    """A file ``.gitignore`` excludes is left out of the scan."""
    _write(tree / ".gitignore", "docs/scratch.rst\n")
    _write(tree / "docs" / "scratch.rst", "It took none.\n")  # wording:ignore
    assert checker.main([], root=tree) == 0


def test_path_limits_the_listing_to_a_subtree(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--path`` narrows the check to the files under it."""
    _write(tree / "docs" / "page.rst", PAGE)
    _write(tree / "backend" / "a.py", '"""It took none."""\n')  # wording:ignore
    checker.main(["--path", "backend"], root=tree)
    out = capsys.readouterr().out
    hit_lines = out.splitlines()[:-1]
    listed = [line.split(":")[0] for line in hit_lines if not line.startswith(" ")]
    assert listed == ["backend/a.py"]


def test_path_passes_for_a_clean_subtree(tree: Path) -> None:
    """A subtree without a hit exits 0, even while another holds some."""
    _write(tree / "backend" / "a.py", '"""It took none."""\n')  # wording:ignore
    assert checker.main(["--path", "docs"], root=tree) == 0


def test_path_is_repeatable(tree: Path) -> None:
    """Two ``--path`` switches check both subtrees, the first as well as the last."""
    _write(tree / "backend" / "a.py", '"""It took none."""\n')  # wording:ignore
    assert checker.main(["--path", "backend/a.py", "--path", "docs"], root=tree) == 1


SKIPPED = {
    "plans": "plans/2026-10-15-sweep.md",
    "critiques": "critiques/2026-10-15-review.md",
    "generated-schema": "frontend/src/portal/api/schema.d.ts",
    "openapi-snapshot": "backend/tests/snapshots/openapi-components.json",
    "lock-file": "frontend/package-lock.json",
    "golden": "backend/tests/golden/report.txt",
    "worktrees": ".claude/worktrees/agent-x/README.rst",
    "docs-build": "docs/_build/html/index.txt",
    "dist": "frontend/dist/assets/app.js",
    "htmlcov": "backend/htmlcov/index.html",
    "staticfiles": "backend/staticfiles/site.css",
    "e2e-mail": "frontend/e2e/.mail/1.eml",
}


@pytest.mark.parametrize("relative", list(SKIPPED.values()), ids=list(SKIPPED))
def test_a_skipped_file_is_never_checked(tree: Path, relative: str) -> None:
    """A file outside the scanned tree, a generated file, or a lock file is skipped."""
    _write(tree / relative, "It took nothing.\n")  # wording:ignore
    assert checker.main([], root=tree) == 0


def test_a_binary_file_is_never_checked(tree: Path) -> None:
    """A file holding a NUL byte is skipped, whatever text it also holds."""
    (tree / "docs" / "image.dat").write_bytes(b"\x00It took nothing.\n")  # wording:ignore
    assert checker.main([], root=tree) == 0


COORDINATED_PAGE = (
    "It gets 400 and no message.\n"  # wording:ignore
    "It is fine, and no email is sent.\n"
    "It reads yes or no.\n"
    "It is quick but no longer free.\n"
)


def _listed(out: str) -> list[str]:
    """The ``path:line`` of each listed entry in ``out``."""
    return [":".join(line.split(":")[:2]) for line in out.splitlines() if ": " in line]


def test_coordinated_lists_each_conjunction_before_a_negative(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--coordinated`` lists the object and the subject alike, for review by hand.

    "or no." is an answer and "but no longer" an idiom, so neither is listed.
    """
    _write(tree / "docs" / "other.rst", COORDINATED_PAGE)
    checker.main(["--coordinated", "--path", "docs/other.rst"], root=tree)
    assert _listed(capsys.readouterr().out) == ["docs/other.rst:1", "docs/other.rst:2"]


def test_coordinated_always_exits_0(tree: Path) -> None:
    """A candidate is for review, never a failure."""
    _write(tree / "docs" / "other.rst", COORDINATED_PAGE)
    assert checker.main(["--coordinated"], root=tree) == 0


def test_coordinated_candidates_are_never_hits(tree: Path) -> None:
    """The check itself passes over the conjunctions."""
    _write(tree / "docs" / "other.rst", COORDINATED_PAGE)
    _track(tree)
    assert checker.main([], root=tree) == 0


def test_coordinated_skips_a_marked_line(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A reviewed candidate kept with the marker stays out of the listing."""
    _write(
        tree / "docs" / "other.rst", f"It gets 400 and no message. .. {MARKER}\n"
    )  # wording:ignore
    checker.main(["--coordinated", "--path", "docs/other.rst"], root=tree)
    assert _listed(capsys.readouterr().out) == []


# -- the wiring ------------------------------------------------------------------


def test_make_lint_runs_the_wording_check() -> None:
    """``make lint`` depends on ``lint-wording``."""
    text = MAKEFILE.read_text(encoding="utf-8")
    lint_line = next(line for line in text.splitlines() if line.startswith("lint:"))
    assert "lint-wording" in lint_line.split("##")[0]


def test_ci_runs_the_wording_check() -> None:
    """CI lists its lint targets one by one, so it names ``lint-wording`` itself."""
    assert "run: make lint-wording" in CI_WORKFLOW.read_text(encoding="utf-8")


def test_the_script_is_executable() -> None:
    """The committed file carries its executable bit, so ``./scripts/...`` runs it."""
    assert os.access(SCRIPT, os.X_OK)
