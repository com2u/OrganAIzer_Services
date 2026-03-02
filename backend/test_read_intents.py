"""Quick acceptance test for EMAIL_READ / CALENDAR_READ routing."""
import sys
sys.path.insert(0, ".")

from utils.intent_router import IntentRouter, IntentType
from utils.slot_extraction import SlotExtractor

CALENDAR_READ_OR_LIST = "CALENDAR_READ_OR_LIST"

routing_tests = [
    # ── Email READ ────────────────────────────────────────────────────────────
    ("What are my last 3 emails?",          IntentType.EMAIL_READ),
    ("Show me my last 5 emails",            IntentType.EMAIL_READ),
    ("Do I have any new emails?",           IntentType.EMAIL_READ),
    ("Any unread emails?",                  IntentType.EMAIL_READ),
    ("What emails did I get yesterday?",    IntentType.EMAIL_READ),
    ("Check my inbox",                      IntentType.EMAIL_READ),
    ("Summarize my emails",                 IntentType.EMAIL_READ),
    # ── Calendar READ ─────────────────────────────────────────────────────────
    ("What is on my calendar today?",       CALENDAR_READ_OR_LIST),
    ("Do I have anything tomorrow?",        IntentType.CALENDAR_READ),
    ("What meetings do I have next Friday?",IntentType.CALENDAR_READ),
    ("When is my next meeting?",            IntentType.CALENDAR_READ),
    ("Do I have anything this week?",       IntentType.CALENDAR_READ),
    ("What did I have yesterday?",          IntentType.CALENDAR_READ),
    ("My schedule",                         IntentType.CALENDAR_READ),
    # ── NOT email read ────────────────────────────────────────────────────────
    ("Send an email to john@example.com",   IntentType.GENERAL_MESSAGE),
]

passed = failed = 0
for msg, expected in routing_tests:
    r = IntentRouter.route_message(msg, None, None)
    got = r["intent_type"]
    ok = (got == expected) or (expected == CALENDAR_READ_OR_LIST and got in (IntentType.CALENDAR_LIST, IntentType.CALENDAR_READ))
    if ok:
        passed += 1
        print(f"  PASS [{got}] <- \"{msg}\"")
    else:
        failed += 1
        print(f"  FAIL [{got}] (expected {expected}) <- \"{msg}\"")

print(f"\n── Routing: {passed}/{passed+failed} passed ──\n")

# ── Slot extraction tests ─────────────────────────────────────────────────────
slot_tests = [
    ("What are my last 3 emails?",       "email",    {"count": 3, "unread_only": False}),
    ("Any unread emails?",               "email",    {"unread_only": True}),
    ("What emails did I get yesterday?", "email",    {"date_filter": "yesterday"}),
    ("Summarize today emails",           "email",    {"date_filter": "today"}),
    ("When is my next meeting?",         "calendar", {"next_event": True}),
    ("Do I have anything today?",        "calendar", {"date_label": "today"}),
    ("Do I have anything this week?",    "calendar", {"date_label": "this week"}),
    ("What do I have next week?",        "calendar", {"date_label": "next week"}),
]

sp = sf = 0
for msg, kind, expected_slots in slot_tests:
    if kind == "email":
        got = SlotExtractor.extract_email_read_slots(msg)
    else:
        got = SlotExtractor.extract_calendar_read_slots(msg)
    ok = all(got.get(k) == v for k, v in expected_slots.items())
    if ok:
        sp += 1
        print(f"  PASS slots [{msg}] -> {expected_slots}")
    else:
        sf += 1
        actual = {k: got.get(k) for k in expected_slots}
        print(f"  FAIL slots [{msg}] expected {expected_slots} got {actual}")

print(f"\n── Slots: {sp}/{sp+sf} passed ──")
print(f"\n=== TOTAL: {passed+sp}/{passed+failed+sp+sf} passed ===")
