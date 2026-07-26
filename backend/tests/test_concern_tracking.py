"""
Unit tests for voice/concern_tracking.py — the small per-call tracker for
multiple caller concerns mentioned in one call.

No FreeSWITCH, no ESL, no LLM. Pure function-level tests, mirroring the
style of test_human_handoff_dialogue.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import concern_tracking as ct  # noqa: E402


# =============================================================================
# Explicit multi-intent marker detection — conservative, no semantic parsing
# =============================================================================

class TestMultiIntentDetection:
    def test_ordinary_und_without_explicit_marker_is_not_split(self):
        # "Mein Telefon klingelt nicht und unser WLAN ist auch schlecht." —
        # a real two-concern utterance, but with plain "und", not an explicit
        # marker ("und außerdem", "zusätzlich", ...). Conservative-by-design:
        # must NOT split (see test_explicit_marker_* below for the positive
        # "two concerns in one utterance" case that DOES split).
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "Mein Telefon klingelt nicht und unser WLAN ist auch schlecht.",
        )
        assert record is None
        assert ct.open_concerns(state) == []

    def test_two_concerns_in_one_utterance_with_explicit_marker(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "Ich brauche Hilfe mit Outlook und außerdem möchte ich einen Termin.",
        )
        assert record is not None
        assert "termin" in record["text"].lower()
        assert len(ct.open_concerns(state)) == 1

    def test_explicit_marker_zusaetzlich(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "Das Internet ist ausgefallen, zusätzlich wollte ich nach einer neuen Anlage fragen.",
        )
        assert record is not None
        assert "anlage" in record["text"].lower()

    def test_three_concerns_across_several_turns(self):
        state = ct.new_state()
        ct.observe_turn(state, "Das Telefon geht nicht und außerdem ist das WLAN langsam.")
        ct.observe_turn(state, "Zusätzlich habe ich noch eine Frage zur Rechnung.")
        ct.observe_turn(state, "Und dazu wollte ich noch einen Rückruf vereinbaren.")
        assert len(state) == 3
        assert all(c["status"] == "open" for c in state)

    def test_no_false_positive_from_ordinary_und_inside_one_sentence(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state, "Ich habe ein Problem mit meinem Telefon und mit meinem Router."
        )
        assert record is None
        assert ct.open_concerns(state) == []

    def test_english_marker_and_also(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state, "I need help with Outlook and also I'd like to book an appointment."
        )
        assert record is not None
        assert "appointment" in record["text"].lower()

    def test_english_ordinary_and_no_false_positive(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state, "My phone and my WiFi are both not working."
        )
        assert record is None

    def test_empty_utterance_returns_none(self):
        assert ct.observe_turn(ct.new_state(), "") is None

    def test_marker_with_nothing_after_it_returns_none(self):
        state = ct.new_state()
        assert ct.observe_turn(state, "Und außerdem") is None
        assert ct.open_concerns(state) == []

    def test_repeated_identical_concern_not_added_twice(self):
        state = ct.new_state()
        ct.observe_turn(state, "Telefon kaputt und außerdem ist das WLAN langsam.")
        ct.observe_turn(state, "Wie gesagt, und außerdem ist das WLAN langsam.")
        assert len(state) == 1


# =============================================================================
# Priority — emergency > outage > operational > appointment > informational
# =============================================================================

class TestPriorityOrdering:
    def test_emergency_ranks_first(self):
        assert ct.classify_category("es ist ein notfall") == "emergency"
        assert ct._priority_rank("emergency") == 0

    def test_outage_ranks_second(self):
        assert ct.classify_category("kompletter ausfall der anlage") == "outage"
        assert ct._priority_rank("outage") == 1

    def test_appointment_ranks_fourth(self):
        assert ct.classify_category("ich hätte gern einen termin") == "appointment"
        assert ct._priority_rank("appointment") == 3

    def test_informational_ranks_last(self):
        assert ct.classify_category("wie viel kostet eine neue anlage") == "informational"
        assert ct._priority_rank("informational") == 4

    def test_urgent_concern_prioritized_first_among_open_concerns(self):
        state = ct.new_state()
        ct.observe_turn(state, "Ich habe eine Frage und außerdem hätte ich gern einen Termin.")
        ct.observe_turn(state, "Übrigens, zusätzlich ist es ein notfall, es brennt.")
        open_ = ct.open_concerns(state)
        highest = min(open_, key=lambda c: c["priority"])
        assert highest["category"] == "emergency"


# =============================================================================
# Status lifecycle — open / resolved / handed_off
# =============================================================================

class TestConcernStatusLifecycle:
    def test_resolved_concern_excluded_from_open_concerns(self):
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem Problem B mit dem Router.")
        assert len(ct.open_concerns(state)) == 1
        text = state[0]["text"]
        assert ct.mark_resolved(state, text[:10]) is True
        # Resolved concern must not be repeated in a handoff — i.e. must not
        # appear in open_concerns(), which is the only source handoff/
        # escalation/call-log wiring reads from.
        assert ct.open_concerns(state) == []
        assert state[0]["status"] == "resolved"

    def test_mark_resolved_returns_false_when_nothing_matches(self):
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem Problem B.")
        assert ct.mark_resolved(state, "völlig anderer text") is False
        assert len(ct.open_concerns(state)) == 1

    def test_mark_all_handed_off(self):
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem Problem B mit dem Router.")
        ct.mark_all_handed_off(state)
        assert ct.open_concerns(state) == []
        assert state[0]["status"] == "handed_off"

    def test_handed_off_concern_not_marked_handed_off_twice_incorrectly(self):
        # mark_all_handed_off only touches OPEN concerns — a concern already
        # resolved must stay "resolved", not get silently overwritten.
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem Problem B.")
        ct.mark_resolved(state, state[0]["text"][:10])
        ct.mark_all_handed_off(state)
        assert state[0]["status"] == "resolved"


# =============================================================================
# Prompt extra + acknowledgement wording
# =============================================================================

class TestPromptExtraAndAcknowledgement:
    def test_no_open_concerns_returns_none(self):
        assert ct.build_prompt_extra(ct.new_state()) is None

    def test_single_open_concern_extra(self):
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem Problem B mit dem Router.")
        extra = ct.build_prompt_extra(state)
        assert extra is not None
        assert "Problem B" in extra or "problem b" in extra.lower()

    def test_acknowledgement_does_not_quote_raw_caller_text(self):
        # Must not attempt to grammatically embed an arbitrary caller
        # fragment — see the function's own docstring reasoning.
        ack_de = ct.acknowledgement_for_new_concern(2, lang="de")
        ack_en = ct.acknowledgement_for_new_concern(2, lang="en")
        assert isinstance(ack_de, str) and ack_de
        assert isinstance(ack_en, str) and ack_en
        assert ack_de != ack_en

    def test_acknowledgement_singular_vs_plural_wording_differs(self):
        single = ct.acknowledgement_for_new_concern(1, lang="de")
        plural = ct.acknowledgement_for_new_concern(3, lang="de")
        assert single != plural


# =============================================================================
# Enumeration detection — "das sind drei Dinge" openings (live-call regression)
# =============================================================================

class TestEnumerationDetection:
    # The exact opening utterance from the 2026-07-25 live test call that the
    # marker-tail approach missed: three concerns first, count phrase last.
    # Verbatim (including the STT cut-off "die ich..."): the trailing modal
    # heuristic in esl_call_handler treats "...wollte."-style endings as
    # unfinished, so a paraphrase ending in a modal verb would never even
    # reach this tracker in the live loop.
    _LIVE_OPENING = (
        "Ja, also wie gesagt, das Internet funktioniert nicht seit zwei Tagen. "
        "Die Telefonanlage muss inspeziert werden. "
        "Und ich habe eine Frage zur Rechnung von der letzten Woche. "
        "Das sind drei Dinge, die ich..."
    )

    def test_live_transcript_three_concern_opening_captures_two_additional(self):
        state = ct.new_state()
        record = ct.observe_turn(state, self._LIVE_OPENING)
        assert record is not None
        assert len(state) == 2
        texts = [c["text"].lower() for c in state]
        assert any("telefonanlage" in t for t in texts)
        assert any("rechnung" in t for t in texts)
        assert all(c["status"] == "open" for c in state)

    def test_count_mismatch_captures_nothing(self):
        # Stated three, but only one content sentence — no guessing, no split.
        state = ct.new_state()
        record = ct.observe_turn(
            state, "Das Internet geht nicht. Das sind drei Dinge."
        )
        assert record is None
        assert state == []

    def test_count_word_without_enumeration_noun_is_ignored(self):
        # "zwei Tagen" must never read as an enumeration.
        state = ct.new_state()
        record = ct.observe_turn(
            state, "Das Internet funktioniert nicht seit zwei Tagen."
        )
        assert record is None
        assert state == []

    def test_count_mismatch_falls_back_to_marker_tail(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "Das Internet geht nicht und außerdem brauche ich einen Termin. "
            "Das sind fünf Punkte.",
        )
        assert record is not None
        assert len(state) == 1
        assert "termin" in state[0]["text"].lower()

    def test_repeated_enumeration_is_deduplicated(self):
        state = ct.new_state()
        assert ct.observe_turn(state, self._LIVE_OPENING) is not None
        assert ct.observe_turn(state, self._LIVE_OPENING) is None
        assert len(state) == 2

    def test_english_enumeration(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "The internet is down. I need an appointment. "
            "I have a question about my invoice. Those are three things.",
        )
        assert record is not None
        assert len(state) == 2
        assert any(c["category"] == "appointment" for c in state)

    def test_trailing_shape_records_the_stated_count(self):
        # The count is remembered for both shapes — here it matches what was
        # actually tracked (2 records + the topic being handled = 3).
        state = ct.new_state()
        ct.observe_turn(state, self._LIVE_OPENING)
        assert ct.expected_count(state) == 3
        assert len(state) + 1 == ct.expected_count(state)


# =============================================================================
# Leading enumeration — live-call regression, call 20260725_182617_016092486631
#
# The caller opened with "ich habe eigentlich drei Dinge" as a PREAMBLE and
# then described only concern #1 (the internet outage) before STT cut them
# off. The exact-count guard passed by coincidence — STT punctuated that one
# complaint into exactly three sentences — so two fragments of a single topic
# were stored as two "concerns". Downstream that surfaced as a vague "die
# weiteren Fragen" in the pre-transfer question, while the caller's real
# second and third topics (Telefonanlage-Termin, Rechnung) were never tracked
# at all, because they were never actually spoken in that turn.
# =============================================================================

class TestLeadingEnumerationNotSplit:
    # Verbatim first caller turn from the live transcript, including the STT
    # cut-off "Die Lichter sind alle...".
    _LIVE_LEADING_OPENING = (
        "Guten Tag, ich habe eigentlich drei Dinge, die ich mit Ihnen besprechen "
        "möchte.  Zum einen habe wir seit gestern ein Problem mit unserem "
        "Internet.  Wir haben einen Rodefoneanschluss und die Verbindung ist "
        "komplett weg. Die Lichter sind alle..."
    )

    def test_live_leading_opening_creates_no_concern_records(self):
        state = ct.new_state()
        record = ct.observe_turn(state, self._LIVE_LEADING_OPENING)
        assert record is None
        assert list(state) == []
        # Specifically: the two internet-description fragments that used to be
        # stored as separate concerns.
        texts = " ".join(c["text"].lower() for c in state)
        assert "lichter" not in texts
        assert "rodefone" not in texts

    def test_live_leading_opening_remembers_the_promised_count(self):
        state = ct.new_state()
        ct.observe_turn(state, self._LIVE_LEADING_OPENING)
        assert ct.expected_count(state) == 3

    def test_no_misleading_plural_acknowledgement_fires(self):
        # observe_turn returning None is what suppresses the spoken
        # "Verstanden — die weiteren Punkte ..." prefix at the call site; the
        # plural wording specifically requires open_count > 1.
        state = ct.new_state()
        assert ct.observe_turn(state, self._LIVE_LEADING_OPENING) is None
        assert len(ct.open_concerns(state)) == 0

    def test_final_note_hedges_when_tracked_falls_short_of_promise(self):
        state = ct.new_state()
        ct.observe_turn(state, self._LIVE_LEADING_OPENING)
        ct.observe_turn(state, "Zusätzlich habe ich eine Frage zur Rechnung.")
        # One tracked + the topic being handled = 2, but three were announced:
        # naming "die weitere Frage" would imply that is all that is left.
        assert ct.open_category_labels(state) == "die weitere Frage"
        assert ct.final_note_labels(state) is None

    def test_final_note_names_categories_once_the_promise_is_met(self):
        state = ct.new_state()
        ct.observe_turn(state, self._LIVE_LEADING_OPENING)
        ct.observe_turn(state, "Zusätzlich habe ich eine Frage zur Rechnung.")
        ct.observe_turn(state, "Und dazu wollte ich noch einen Termin vereinbaren.")
        assert ct.expected_count(state) == 3
        assert len(state) + 1 == 3
        assert ct.final_note_labels(state) == ct.open_category_labels(state)
        assert ct.final_note_labels(state) is not None

    def test_final_note_unaffected_when_no_count_was_ever_stated(self):
        state = ct.new_state()
        ct.observe_turn(state, "Das WLAN spinnt und außerdem hätte ich gern einen Termin.")
        assert ct.expected_count(state) == 0
        assert ct.final_note_labels(state) == ct.open_category_labels(state)

    def test_leading_count_with_coincidentally_matching_sentence_count(self):
        # The heart of the bug: stated count == content-sentence count, but
        # every sentence belongs to ONE topic. Complete punctuation here, so
        # only the leading/trailing rule can reject it.
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "Ich habe drei Anliegen. Das Internet ist weg. "
            "Der Router blinkt rot. Nichts geht mehr.",
        )
        assert record is None
        assert list(state) == []
        assert ct.expected_count(state) == 3

    def test_leading_enumeration_still_falls_back_to_marker_tail(self):
        # Refusing to split must not swallow an explicit marker in the same
        # utterance — the marker-tail path is untouched.
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "Ich habe drei Dinge. Das Internet ist weg und außerdem "
            "hätte ich gern einen Termin.",
        )
        assert record is not None
        assert len(state) == 1
        assert "termin" in state[0]["text"].lower()


# =============================================================================
# Truncated transcriptions never become concern records
# =============================================================================

class TestIncompleteUtteranceGate:
    def test_training_case_trailing_cutoff_is_tolerated(self):
        # "Das sind drei Dinge, die ich..." — the truncated fragment IS the
        # meta count sentence, which is discarded anyway, so the three
        # complete concern sentences before it are still safe to split.
        assert ct._final_fragment_is_incomplete(
            "Das sind drei Dinge, die ich..."
        ) is True
        state = ct.new_state()
        assert ct.observe_turn(
            state, TestEnumerationDetection._LIVE_OPENING
        ) is not None
        assert len(state) == 2

    def test_failing_case_content_cutoff_is_rejected(self):
        assert ct._final_fragment_is_incomplete(
            "Die Lichter sind alle..."
        ) is True
        state = ct.new_state()
        assert ct.observe_turn(
            state, TestLeadingEnumerationNotSplit._LIVE_LEADING_OPENING
        ) is None
        assert list(state) == []

    def test_missing_terminal_punctuation_counts_as_incomplete(self):
        assert ct._final_fragment_is_incomplete("Die Lichter sind alle") is True
        assert ct._final_fragment_is_incomplete("Das Internet ist weg.") is False
        assert ct._final_fragment_is_incomplete("Ist das Internet weg?") is False
        assert ct._final_fragment_is_incomplete("Das Internet ist weg!  ") is False
        assert ct._final_fragment_is_incomplete("") is True

    def test_unicode_ellipsis_treated_like_three_dots(self):
        assert ct._final_fragment_is_incomplete("Die Lichter sind alle…") is True

    def test_truncated_tail_blocks_split_even_in_trailing_shape(self):
        # Count phrase last, exact count match — but the utterance was cut
        # off inside a sentence that would have become a concern, so the
        # sentence count is not trustworthy.
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "Das Internet ist weg. Die Telefonanlage muss geprüft werden. "
            "Das sind zwei Dinge. Und dann noch die Sache mit dem...",
        )
        assert record is None
        assert list(state) == []


# =============================================================================
# Category labels + deterministic handover summary (spoken escalation lines)
# =============================================================================

class TestCategoryLabelsAndHandoverSummary:
    def _two_concern_state(self):
        state = ct.new_state()
        ct.observe_turn(state, "Das WLAN spinnt und außerdem hätte ich gern einen Termin.")
        ct.observe_turn(state, "Zusätzlich habe ich eine Frage zur Rechnung.")
        assert [c["category"] for c in state] == ["appointment", "informational"]
        return state

    def test_open_category_labels_none_when_empty(self):
        assert ct.open_category_labels(ct.new_state()) is None

    def test_open_category_labels_never_contain_raw_caller_text(self):
        state = self._two_concern_state()
        labels = ct.open_category_labels(state)
        assert labels == "die Terminanfrage und die weitere Frage"
        assert "wlan" not in labels.lower()
        assert "rechnung" not in labels.lower()

    def test_open_category_labels_plural_when_category_repeats(self):
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem eine Frage zur Rechnung.")
        ct.observe_turn(state, "Zusätzlich noch eine Frage zum Vertrag bitte.")
        assert ct.open_category_labels(state) == "die weiteren Fragen"

    def test_handover_summary_none_when_no_records(self):
        assert ct.handover_summary_sentence(ct.new_state()) is None

    def test_handover_summary_open_only(self):
        state = self._two_concern_state()
        assert ct.handover_summary_sentence(state) == (
            "Ihre weiteren Anliegen — die Terminanfrage und die weitere Frage — "
            "gebe ich mit an den Mitarbeiter weiter."
        )

    def test_handover_summary_resolved_and_open(self):
        state = self._two_concern_state()
        termin_text = next(c["text"] for c in state if c["category"] == "appointment")
        assert ct.mark_resolved(state, termin_text[:10]) is True
        assert ct.handover_summary_sentence(state) == (
            "Die Terminanfrage haben wir bereits geklärt — "
            "die weitere Frage gebe ich mit an den Mitarbeiter weiter."
        )

    def test_handover_summary_resolved_only(self):
        state = self._two_concern_state()
        for c in state:
            assert ct.mark_resolved(state, c["text"][:10]) is True
        summary = ct.handover_summary_sentence(state)
        assert summary is not None
        assert "bereits geklärt" in summary
        assert "übernimmt der Mitarbeiter" in summary


# =============================================================================
# Unknown categories are loud, not silent — a category that grew in
# classify_category() without _PRIORITY_ORDER / _CATEGORY_LABELS_DE growing
# with it used to vanish from the spoken lines with no trace.
# =============================================================================

class TestUnknownCategoryIsLoud:
    def _state_with_unknown_category(self):
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem hätte ich gern einen Termin.")
        state[0]["category"] = "brandneue_kategorie"
        return state

    def test_priority_rank_warns_and_ranks_least_urgent(self, caplog):
        with caplog.at_level("WARNING", logger="voice.concern_tracking"):
            rank = ct._priority_rank("brandneue_kategorie")
        assert rank == len(ct._PRIORITY_ORDER) - 1
        assert "brandneue_kategorie" in caplog.text

    def test_missing_label_warns_instead_of_silently_dropping(self, caplog):
        state = self._state_with_unknown_category()
        with caplog.at_level("WARNING", logger="voice.concern_tracking"):
            labels = ct.open_category_labels(state)
        assert "brandneue_kategorie" in caplog.text
        # Still no raw caller text, and the line stays speakable.
        assert labels == ""

    def test_known_categories_still_rendered_alongside_an_unknown_one(self, caplog):
        state = self._state_with_unknown_category()
        ct.observe_turn(state, "Zusätzlich habe ich eine Frage zur Rechnung.")
        with caplog.at_level("WARNING", logger="voice.concern_tracking"):
            labels = ct.open_category_labels(state)
        assert labels == "die weitere Frage"
        assert "brandneue_kategorie" in caplog.text

    def test_known_categories_keep_priority_order(self):
        # Ordering now comes from sorting the tracked records, not from
        # walking _PRIORITY_ORDER — most urgent must still come first.
        state = ct.new_state()
        ct.observe_turn(state, "Frage A und außerdem eine Frage zur Rechnung.")
        ct.observe_turn(state, "Zusätzlich hätte ich gern einen Termin.")
        ct.observe_turn(state, "Und dazu, es ist ein notfall, es brennt.")
        assert ct.open_category_labels(state) == (
            "der Notfall, die Terminanfrage und die weitere Frage"
        )

