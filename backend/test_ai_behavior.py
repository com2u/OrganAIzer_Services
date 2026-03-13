"""Quick smoke tests for the AI behavior changes."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from utils.intent_router import IntentRouter, IntentType
from utils.slot_extraction import SlotExtractor

errors = []

# ── Test 1: Event title integrity ────────────────────────────────────────────
slots = SlotExtractor.extract_calendar_slots("Create event Meeting with Chef at 08:00")
title = slots.get("title")
if title == "Meeting with Chef":
    print(f"PASS: title integrity  -> '{title}'")
else:
    errors.append(f"FAIL: title integrity   expected 'Meeting with Chef', got '{title}'")

# ── Test 2: CALENDAR_UPDATE – rename pattern ──────────────────────────────────
result = IntentRouter.route_message("Rename lunch with Anna to lunch with Patrick", None, None)
if result["intent_type"] == IntentType.CALENDAR_UPDATE:
    print("PASS: rename -> CALENDAR_UPDATE")
else:
    errors.append(f"FAIL: rename intent -> got {result['intent_type']}")

# ── Test 3: Calendar create detected ─────────────────────────────────────────
result = IntentRouter.route_message("Create event test at 3pm tomorrow", None, None)
if result["intent_type"] == IntentType.CALENDAR_CREATE:
    print("PASS: calendar create detected")
else:
    errors.append(f"FAIL: calendar create -> got {result['intent_type']}")

# ── Test 4: Update slots – time shift ────────────────────────────────────────
update_slots = SlotExtractor.extract_calendar_update_slots("Move my 3pm meeting to 4pm")
new_time = update_slots.get("new_time")
if new_time == "16:00":
    print(f"PASS: update slots new_time -> '{new_time}'")
else:
    errors.append(f"FAIL: update slots new_time expected '16:00', got '{new_time}' | slots={update_slots}")

# ── Test 5a: Provider lock – Google ──────────────────────────────────────────
p = SlotExtractor._extract_provider("create in google calendar")
if p == "google":
    print("PASS: provider locked to google")
else:
    errors.append(f"FAIL: google provider -> got {p}")

# ── Test 5b: Provider lock – Outlook ─────────────────────────────────────────
p2 = SlotExtractor._extract_provider("use outlook for this")
if p2 == "outlook":
    print("PASS: provider locked to outlook")
else:
    errors.append(f"FAIL: outlook provider -> got {p2}")

# ── Test 6: Rename update slots ───────────────────────────────────────────────
rename_slots = SlotExtractor.extract_calendar_update_slots("Rename lunch with Anna to lunch with Patrick")
if rename_slots.get("new_title") == "lunch with Patrick" and "Anna" in rename_slots.get("search_query", ""):
    print(f"PASS: rename slots -> new_title='{rename_slots.get('new_title')}' search_query='{rename_slots.get('search_query')}'")
else:
    errors.append(f"FAIL: rename slots -> {rename_slots}")

# ── Test 7: Email send -> CALENDAR_CREATE vs EMAIL_SEND ───────────────────────
result = IntentRouter.route_message("Send an email to anna@example.com about the report", None, None)
if result["intent_type"] == IntentType.EMAIL_SEND:
    print("PASS: email send intent")
else:
    errors.append(f"FAIL: email send intent -> got {result['intent_type']}")

# ── Test 8: Title not rewritten ───────────────────────────────────────────────
slots2 = SlotExtractor.extract_calendar_slots("Create event Meeting with Chef at 08:00")
# Title should NOT be rewritten to "Chef Meeting" or "Meeting"
t = slots2.get("title", "")
if "Chef" in t and t != "Chef Meeting" and t != "Meeting":
    print(f"PASS: title not rewritten  -> '{t}'")
else:
    errors.append(f"FAIL: title possibly rewritten -> '{t}'")

print()
if errors:
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
