"""The word lists ``scripts/check_wording.py`` reads, kept apart from the check itself.

Every decision about a word lives here: the verb families the check flags, the other
words it flags (the forms of "be" and the prepositions), the words it deliberately
leaves alone, and the small tables that shape a match or a suggestion.  To change what
is flagged, edit a tuple here; ``backend/tests/test_check_wording.py`` holds the lists
to their invariants (five forms per family, each word listed once, flagged and allowed
disjoint).
"""

# The verbs the check flags, one family per string: base form, third person singular,
# simple past, past participle, and present participle.  The list was built by
# extracting every word that precedes ``no``, ``nothing``, ``nobody``, or ``none`` in the
# scanned tree and keeping each one that can act as a verb (possession or action), with
# its other forms, plus common verbs the tree doesn't use yet; an unlisted ``-ed`` word is
# flagged too (see ``NOT_PAST_TENSE``).  A word that is also a
# noun ("changes", "records", "names") is flagged anyway: a determiner before it already
# marks the plain noun use, and a rewrite costs less than a missed hit.  Linking verbs
# are flagged only where the phrase reads as a negative object, as "becomes" can.
# A table of short strings, packed several to a line; the formatter would give each its
# own line and more than double the module's length.
# fmt: off
FLAGGED_VERBS = (
    "accept accepts accepted accepted accepting",
    "accompany accompanies accompanied accompanied accompanying",
    "accrue accrues accrued accrued accruing", "activate activates activated activated activating",
    "add adds added added adding", "affect affects affected affected affecting",
    "alert alerts alerted alerted alerting", "allow allows allowed allowed allowing",
    "alter alters altered altered altering", "answer answers answered answered answering",
    "apply applies applied applied applying", "approve approves approved approved approving",
    "ask asks asked asked asking", "assert asserts asserted asserted asserting",
    "assign assigns assigned assigned assigning", "assume assumes assumed assumed assuming",
    "attach attaches attached attached attaching", "award awards awarded awarded awarding",
    "bear bears bore borne bearing", "become becomes became become becoming",
    "bill bills billed billed billing", "bind binds bound bound binding",
    "block blocks blocked blocked blocking", "break breaks broke broken breaking",
    "bring brings brought brought bringing", "build builds built built building",
    "buy buys bought bought buying", "call calls called called calling",
    "cancel cancels canceled canceled canceling", "cap caps capped capped capping",
    "capture captures captured captured capturing", "carry carries carried carried carrying",
    "catch catches caught caught catching", "cause causes caused caused causing",
    "change changes changed changed changing", "charge charges charged charged charging",
    "check checks checked checked checking", "choose chooses chose chosen choosing",
    "cite cites cited cited citing", "claim claims claimed claimed claiming",
    "clear clears cleared cleared clearing", "close closes closed closed closing",
    "collect collects collected collected collecting",
    "commit commits committed committed committing",
    "configure configures configured configured configuring",
    "confirm confirms confirmed confirmed confirming",
    "connect connects connected connected connecting",
    "consume consumes consumed consumed consuming",
    "contact contacts contacted contacted contacting",
    "contain contains contained contained containing",
    "contribute contributes contributed contributed contributing",
    "control controls controlled controlled controlling",
    "convert converts converted converted converting", "copy copies copied copied copying",
    "cost costs cost cost costing", "count counts counted counted counting",
    "cover covers covered covered covering", "create creates created created creating",
    "declare declares declared declared declaring", "decline declines declined declined declining",
    "define defines defined defined defining", "delete deletes deleted deleted deleting",
    "deliver delivers delivered delivered delivering", "deny denies denied denied denying",
    "deploy deploys deployed deployed deploying",
    "describe describes described described describing",
    "detect detects detected detected detecting", "disable disables disabled disabled disabling",
    "display displays displayed displayed displaying", "do does did done doing",
    "document documents documented documented documenting", "draw draws drew drawn drawing",
    "drop drops dropped dropped dropping",
    "duplicate duplicates duplicated duplicated duplicating", "earn earns earned earned earning",
    "edit edits edited edited editing", "email emails emailed emailed emailing",
    "emit emits emitted emitted emitting", "enable enables enabled enabled enabling",
    "encode encodes encoded encoded encoding", "end ends ended ended ending",
    "enforce enforces enforced enforced enforcing", "enter enters entered entered entering",
    "exclude excludes excluded excluded excluding", "execute executes executed executed executing",
    "exempt exempts exempted exempted exempting", "exist exists existed existed existing",
    "expand expands expanded expanded expanding", "expect expects expected expected expecting",
    "expire expires expired expired expiring", "export exports exported exported exporting",
    "expose exposes exposed exposed exposing", "extend extends extended extended extending",
    "fail fails failed failed failing", "fetch fetches fetched fetched fetching",
    "file files filed filed filing", "fill fills filled filled filling",
    "filter filters filtered filtered filtering", "find finds found found finding",
    "finish finishes finished finished finishing", "fire fires fired fired firing",
    "fit fits fitted fitted fitting", "flag flags flagged flagged flagging",
    "flip flips flipped flipped flipping", "fly flies flew flown flying",
    "follow follows followed followed following",
    "forward forwards forwarded forwarded forwarding",
    "gather gathers gathered gathered gathering",
    "generate generates generated generated generating", "get gets got gotten getting",
    "give gives gave given giving", "go goes went gone going",
    "grant grants granted granted granting", "handle handles handled handled handling",
    "have has had had having", "hear hears heard heard hearing",
    "help helps helped helped helping", "hide hides hid hidden hiding", "hit hits hit hit hitting",
    "hold holds held held holding", "host hosts hosted hosted hosting",
    "identify identifies identified identified identifying",
    "ignore ignores ignored ignored ignoring", "imply implies implied implied implying",
    "import imports imported imported importing", "impose imposes imposed imposed imposing",
    "include includes included included including", "incur incurs incurred incurred incurring",
    "infer infers inferred inferred inferring", "inherit inherits inherited inherited inheriting",
    "inject injects injected injected injecting",
    "install installs installed installed installing", "invite invites invited invited inviting",
    "involve involves involved involved involving", "issue issues issued issued issuing",
    "join joins joined joined joining", "keep keeps kept kept keeping",
    "kill kills killed killed killing", "know knows knew known knowing",
    "launch launches launched launched launching", "lay lays laid laid laying",
    "lead leads led led leading", "learn learns learned learned learning",
    "leave leaves left left leaving", "lend lends lent lent lending", "let lets let let letting",
    "lift lifts lifted lifted lifting", "limit limits limited limited limiting",
    "link links linked linked linking", "list lists listed listed listing",
    "load loads loaded loaded loading", "lock locks locked locked locking",
    "log logs logged logged logging", "look looks looked looked looking",
    "lose loses lost lost losing", "mail mails mailed mailed mailing",
    "make makes made made making", "manage manages managed managed managing",
    "mark marks marked marked marking", "match matches matched matched matching",
    "mean means meant meant meaning", "mention mentions mentioned mentioned mentioning",
    "modify modifies modified modified modifying", "mount mounts mounted mounted mounting",
    "move moves moved moved moving", "name names named named naming",
    "narrow narrows narrowed narrowed narrowing", "need needs needed needed needing",
    "notify notifies notified notified notifying", "obtain obtains obtained obtained obtaining",
    "occupy occupies occupied occupied occupying", "offer offers offered offered offering",
    "omit omits omitted omitted omitting", "open opens opened opened opening",
    "orchestrate orchestrates orchestrated orchestrated orchestrating",
    "order orders ordered ordered ordering", "outlive outlives outlived outlived outliving",
    "owe owes owed owed owing", "own owns owned owned owning",
    "paint paints painted painted painting", "parse parses parsed parsed parsing",
    "pass passes passed passed passing", "pay pays paid paid paying",
    "perform performs performed performed performing",
    "permit permits permitted permitted permitting", "pick picks picked picked picking",
    "pin pins pinned pinned pinning", "pipe pipes piped piped piping",
    "place places placed placed placing", "play plays played played playing",
    "pose poses posed posed posing", "post posts posted posted posting",
    "preserve preserves preserved preserved preserving",
    "prevent prevents prevented prevented preventing", "print prints printed printed printing",
    "process processes processed processed processing",
    "produce produces produced produced producing", "promise promises promised promised promising",
    "protect protects protected protected protecting", "prove proves proved proven proving",
    "provide provides provided provided providing",
    "publish publishes published published publishing", "pull pulls pulled pulled pulling",
    "push pushes pushed pushed pushing", "put puts put put putting",
    "queue queues queued queued queuing", "raise raises raised raised raising",
    "reach reaches reached reached reaching",
    "reactivate reactivates reactivated reactivated reactivating", "read reads read read reading",
    "receive receives received received receiving",
    "recognize recognizes recognized recognized recognizing",
    "record records recorded recorded recording",
    "redirect redirects redirected redirected redirecting",
    "reference references referenced referenced referencing",
    "refund refunds refunded refunded refunding", "refuse refuses refused refused refusing",
    "register registers registered registered registering",
    "reject rejects rejected rejected rejecting", "release releases released released releasing",
    "remain remains remained remained remaining", "remind reminds reminded reminded reminding",
    "remove removes removed removed removing", "render renders rendered rendered rendering",
    "renew renews renewed renewed renewing", "repeat repeats repeated repeated repeating",
    "replace replaces replaced replaced replacing", "report reports reported reported reporting",
    "request requests requested requested requesting",
    "require requires required required requiring",
    "resemble resembles resembled resembled resembling",
    "reserve reserves reserved reserved reserving", "reset resets reset reset resetting",
    "resolve resolves resolved resolved resolving",
    "respect respects respected respected respecting",
    "restore restores restored restored restoring",
    "restrict restricts restricted restricted restricting",
    "retain retains retained retained retaining", "retry retries retried retried retrying",
    "return returns returned returned returning", "reveal reveals revealed revealed revealing",
    "revoke revokes revoked revoked revoking", "rewrite rewrites rewrote rewritten rewriting",
    "run runs ran run running", "satisfy satisfies satisfied satisfied satisfying",
    "save saves saved saved saving", "say says said said saying",
    "schedule schedules scheduled scheduled scheduling",
    "search searches searched searched searching", "see sees saw seen seeing",
    "seed seeds seeded seeded seeding", "seek seeks sought sought seeking",
    "seem seems seemed seemed seeming", "select selects selected selected selecting",
    "sell sells sold sold selling", "send sends sent sent sending",
    "serve serves served served serving", "set sets set set setting",
    "settle settles settled settled settling", "share shares shared shared sharing",
    "ship ships shipped shipped shipping", "show shows showed shown showing",
    "sign signs signed signed signing", "signal signals signaled signaled signaling",
    "skip skips skipped skipped skipping", "spawn spawns spawned spawned spawning",
    "specify specifies specified specified specifying", "spend spends spent spent spending",
    "stack stacks stacked stacked stacking", "stamp stamps stamped stamped stamping",
    "start starts started started starting", "stay stays stayed stayed staying",
    "store stores stored stored storing", "strip strips stripped stripped stripping",
    "submit submits submitted submitted submitting",
    "suggest suggests suggested suggested suggesting",
    "supply supplies supplied supplied supplying",
    "support supports supported supported supporting",
    "surface surfaces surfaced surfaced surfacing", "tag tags tagged tagged tagging",
    "take takes took taken taking", "tell tells told told telling",
    "terminate terminates terminated terminated terminating", "test tests tested tested testing",
    "throw throws threw thrown throwing", "touch touches touched touched touching",
    "track tracks tracked tracked tracking",
    "transfer transfers transferred transferred transferring",
    "translate translates translated translated translating",
    "treat treats treated treated treating", "trigger triggers triggered triggered triggering",
    "trust trusts trusted trusted trusting",
    "unaffiliate unaffiliates unaffiliated unaffiliated unaffiliating",
    "undo undoes undid undone undoing", "unlock unlocks unlocked unlocked unlocking",
    "unsubscribe unsubscribes unsubscribed unsubscribed unsubscribing",
    "update updates updated updated updating", "upload uploads uploaded uploaded uploading",
    "use uses used used using", "validate validates validated validated validating",
    "verify verifies verified verified verifying", "want wants wanted wanted wanting",
    "warn warns warned warned warning", "work works worked worked working",
    "write writes wrote written writing", "yield yields yielded yielded yielding",
)
# fmt: on

# The words found before a negative that are deliberately left alone, one group per
# string.  Modals ("may no longer") always wait for a verb.  Conjunctions, relative words,
# and adverbs introduce a negative subject ("so no reset email was sent", "when nobody
# is signed in"), which the rule allows.  ``than`` compares with zero ("more than
# nothing").  A pronoun ("it", "them", "you") isn't a verb; the check reads past one to
# the verb before it.  A word in neither tuple is left alone too: this one records the
# decisions.  To flag a word listed here, move it to ``FLAGGED_WORDS``.
#: The modals, which always wait for a verb.
MODALS = "can could may might must shall should will would"

ALLOWED_WORDS = (
    # Modals.
    MODALS,
    # Conjunctions, relative words, and adverbs, which introduce a negative subject.
    "after alone although and because before but deliberately else here if nor once only",
    "or otherwise possibly simply since so that then there though until when where",
    "whereas whether which while who whom why yet",
    # Comparison with zero.
    "than",
    # Pronouns, articles, and the rest.
    "it not sure the them true you",
)

# Words that are not verb families but are flagged all the same, one group per string.
# A form of "be" puts the negation on its complement, and a preposition on its object,
# as these phrases do, one example per line:
#     is no help; there is no payment; were none  # wording:ignore
#     with no term; for no reason; of no use; at no cost; in no case  # wording:ignore
# Write "isn't any help", "there isn't a payment", or "without a term", or move the
# negation to the verb.
#: The forms of "be", flagged before a negative complement.
BE_FORMS = "am are be been being is was were"

#: The prepositions, flagged before a negative object.
PREPOSITIONS = (
    "about against as at by during for from in into like of on onto over per plus",
    "through to toward towards under upon via with within without",
)

FLAGGED_WORDS = (BE_FORMS, *PREPOSITIONS)

#: The negated form a flagged word other than a verb takes in a suggestion.
NEGATED_WORDS = {
    "am": "am not",
    "are": "aren't",
    "is": "isn't",
    "was": "wasn't",
    "were": "weren't",
    "with": "without",
}

# The small word tables below are packed by hand, as ``FLAGGED_VERBS`` is.
# fmt: off

#: A word ending in ``-ed`` reads as a past tense and is flagged even when no family
#: lists it, except these, which only end in the same letters.
NOT_PAST_TENSE = frozenset((
    "bed", "embed", "exceed", "feed", "hundred", "indeed", "proceed", "red", "shed", "speed",
    "succeed",
))

#: The words the check reads past between the verb and the negative: an indirect object
#: ("costs you nothing") or an adverb ("has almost no room").  # wording:ignore
PRONOUNS = ("her", "him", "it", "me", "them", "us", "you")
ADVERBS = (
    "absolutely", "almost", "also", "deliberately", "hardly", "nearly", "practically",
    "really", "simply", "still", "then", "virtually",
)

#: A word before the verb form that makes it a noun: "a change nobody made".
DETERMINERS = frozenset((
    "a", "an", "any", "each", "every", "her", "his", "its", "my", "our", "some", "the",
    "their", "whose", "your",
))

#: A word after ``no`` that makes it an adverb rather than an object: "no longer", "no
#: deeper than".
NOT_OBJECTS = frozenset((
    "bigger", "closer", "deeper", "earlier", "faster", "greater", "higher", "larger", "later",
    "longer", "lower", "matter", "slower", "smaller", "sooner", "wider",
))

# fmt: on

#: A word after ``no`` that takes ``any`` in the rewrite whatever its number.
ANY_BEFORE = frozenset(("fewer", "further", "less", "more", "other", "such"))

#: ``no <word> than`` is a bound, rewritten without the negative: "no more than 255"
#: reads "at most 255".
BOUNDS = {"fewer": "at least", "less": "at least", "more": "at most"}

#: The negative's positive counterpart in a rewrite; ``no`` depends on the next word.
POSITIVES = {"nothing": "anything", "nobody": "anybody", "none": "any"}

#: The perfect auxiliaries a past participle is rewritten with.
PERFECT_AUXILIARIES = frozenset(("had", "has", "have"))

#: The contracted forms of "be" and "have" a negative can follow ("there's no", "we're
#: no", "you've no", "they'd no"), each with its rewrite when a negative object follows
#: it directly: ``'s`` reads as "is", and ``'ve`` and ``'d`` as "have" and "had".
CONTRACTIONS = {"d": "didn't have", "re": "aren't", "s": "isn't", "ve": "don't have"}

#: The same contractions as the auxiliary before a past participle, as in "it isn't
#: sent anything" and "they hadn't sent anything".
CONTRACTED_AUXILIARIES = {"d": "hadn't", "re": "aren't", "s": "isn't", "ve": "haven't"}

#: A word after an ``-ing`` form, an ``-ed`` word, or a participle spelled like its base
#: form that follows ``nobody's``, showing that the ``'s`` is "is" or "has" ("nobody's
#: set up yet", "nobody's charged twice").  A preposition, a pronoun, an adverb, or a
#: determiner there does the same; any other word makes ``nobody's`` a possessive
#: ("nobody's billing address").
PARTICLES = frozenset((
    "again", "away", "back", "down", "off", "once", "out", "twice", "up", "yet",
))  # fmt: skip
