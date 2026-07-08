"""
lang_tracking.py — user/caller-owned conversation-language tracking.

Shared by the phone path (voice/esl_call_handler.py) and the browser voice
mode (api/voice_mode.py) so both surfaces apply the same principle:

    The conversation language belongs to the human, not to the AI.

The language only changes when a user/caller utterance carries strong,
unambiguous evidence of the other language. Short acknowledgements ("Okay.",
"Gut.", "Verstanden.", "Alles klar.") and AI-generated replies must NEVER
change it — re-detecting language from AI output is what caused the
"two receptionists" voice-switching bug on the phone path.

Pure stdlib: no langdetect, no models, no network — safe to import from any
layer without pulling in the telephony or TTS stacks.
"""
from __future__ import annotations

DE_CHARS = frozenset("äöüÄÖÜß")
DE_WORDS = frozenset([
    "ich", "und", "die", "das", "ist", "sie", "der", "ein", "eine",
    "auf", "mit", "von", "für", "nicht", "haben", "kann", "bitte",
    "danke", "gerne", "herr", "frau", "guten",
])

# High-precision English marker words that are NOT also German words.
# Deliberately excludes ambiguous tokens ("in", "an", "man", "was", "also",
# "war", "die", "hat") so German utterances can never look English.
EN_WORDS = frozenset([
    "the", "i", "you", "is", "are", "have", "has", "do", "don't", "would",
    "like", "please", "thank", "thanks", "hello", "yes", "want", "need",
    "can", "could", "should", "my", "your", "help", "speak", "english",
    "appointment", "call", "back", "sorry", "what", "when", "how",
])

# An utterance must have at least this many words before it is allowed to
# change the conversation language. Short acknowledgements ("Okay.", "Ja.",
# "Gut.") carry no reliable language signal and must never flip the voice.
LANG_SWITCH_MIN_WORDS = 4


def update_conversation_language(text: str, current: str) -> str:
    """Return the conversation language after hearing user/caller *text*.

    The conversation language belongs to the human: it only changes when a
    sufficiently long utterance carries unambiguous markers of the other
    language. Anything short or ambiguous keeps *current* — so the AI speaks
    with one consistent voice for the whole conversation.
    """
    words = [w.strip(".,!?;:'\"") for w in text.lower().split()]
    words = [w for w in words if w]
    if len(words) < LANG_SWITCH_MIN_WORDS:
        return current
    wset = set(words)
    has_de = any(c in DE_CHARS for c in text) or bool(wset & DE_WORDS)
    en_hits = len(wset & EN_WORDS)
    if has_de:
        # German markers are high-precision — a real German sentence wins
        # even if it contains loanwords that look English.
        return "de"
    if en_hits >= 2:
        return "en"
    return current
