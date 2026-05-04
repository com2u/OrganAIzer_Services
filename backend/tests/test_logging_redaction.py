"""
Tests for core.logging_config redaction: redact_text() and _redact_value().

All tests are pure-function — no network, no external services, no secrets.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.logging_config import redact_text, _redact_value


# =============================================================================
# Email redaction
# =============================================================================

class TestEmailRedaction:
    def test_plain_email_is_redacted(self):
        result = redact_text("user@example.com")
        assert "user@example.com" not in result
        assert "[REDACTED_EMAIL]" in result

    def test_email_inside_sentence(self):
        result = redact_text("Send the report to alice@domain.org for review")
        assert "alice@domain.org" not in result
        assert "[REDACTED_EMAIL]" in result

    def test_email_inside_json_string(self):
        raw = '{"from": "sender@mail.de", "to": "boss@company.com"}'
        result = redact_text(raw)
        assert "sender@mail.de" not in result
        assert "boss@company.com" not in result

    def test_multiple_emails_all_redacted(self):
        raw = "CC: alice@a.com and bob@b.com"
        result = redact_text(raw)
        assert "alice@a.com" not in result
        assert "bob@b.com" not in result
        assert result.count("[REDACTED_EMAIL]") == 2

    def test_non_email_text_is_unchanged(self):
        raw = "This message contains no email address"
        assert redact_text(raw) == raw

    def test_subdomain_email_redacted(self):
        result = redact_text("user@mail.sub.example.co.uk")
        assert "user@mail.sub.example.co.uk" not in result
        assert "[REDACTED_EMAIL]" in result


# =============================================================================
# Bearer token redaction
# =============================================================================

class TestBearerTokenRedaction:
    def test_bearer_jwt_redacted(self):
        raw = "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig"
        result = redact_text(raw)
        assert "eyJhbGciOiJSUzI1NiJ9" not in result
        assert "Bearer [REDACTED]" in result

    def test_bearer_opaque_token_redacted(self):
        raw = "Authorization: Bearer ya29FakeAccessTokenABCDEFG"
        result = redact_text(raw)
        assert "ya29FakeAccessTokenABCDEFG" not in result
        assert "Bearer [REDACTED]" in result

    def test_bearer_case_insensitive(self):
        raw = "authorization: bearer sk-abc123def456"
        result = redact_text(raw)
        assert "sk-abc123def456" not in result

    def test_bearer_in_json_log(self):
        raw = '{"Authorization": "Bearer eyJtoken123"}'
        result = redact_text(raw)
        assert "eyJtoken123" not in result
        assert "Bearer [REDACTED]" in result


# =============================================================================
# OpenRouter / API key value redaction
# =============================================================================

class TestApiKeyValueRedaction:
    def test_openrouter_key_redacted(self):
        raw = "Using key sk-or-v1-abc123def456ghi789jkl012"
        result = redact_text(raw)
        assert "sk-or-v1-abc123def456ghi789jkl012" not in result
        assert "[REDACTED_API_KEY]" in result

    def test_openai_sk_proj_key_redacted(self):
        raw = "key sk-proj-abcdefghijklmnopqrst12345extra"
        result = redact_text(raw)
        assert "sk-proj-abcdefghijklmnopqrst12345extra" not in result

    def test_google_aiza_key_redacted(self):
        raw = "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234567"
        result = redact_text(raw)
        assert "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234567" not in result
        assert "[REDACTED_API_KEY]" in result

    def test_api_key_assignment_pattern_redacted(self):
        raw = 'api_key: "sk-or-v1-supersecret123456789"'
        result = redact_text(raw)
        assert "sk-or-v1-supersecret123456789" not in result

    def test_x_api_key_header_redacted(self):
        raw = "x-api-key: mysecretapivalue"
        result = redact_text(raw)
        assert "mysecretapivalue" not in result

    def test_access_token_assignment_redacted(self):
        raw = "access_token=ya29FakeTokenXYZ"
        result = redact_text(raw)
        assert "ya29FakeTokenXYZ" not in result
        assert "[REDACTED]" in result

    def test_access_token_colon_redacted(self):
        raw = 'access_token: "1//FakeRefreshABC"'
        result = redact_text(raw)
        assert "1//FakeRefreshABC" not in result


# =============================================================================
# TOKEN_ENCRYPTION_KEY redaction
# =============================================================================

class TestTokenEncryptionKeyRedaction:
    def test_token_encryption_key_equals(self):
        raw = "TOKEN_ENCRYPTION_KEY=supersecretkeyvalue123"
        result = redact_text(raw)
        assert "supersecretkeyvalue123" not in result
        assert "[REDACTED]" in result

    def test_token_encryption_key_colon(self):
        raw = 'token_encryption_key: "anothersecret456"'
        result = redact_text(raw)
        assert "anothersecret456" not in result

    def test_client_secret_assignment_redacted(self):
        raw = "client_secret=GOCSPX-fakeClientSecret123"
        result = redact_text(raw)
        assert "GOCSPX-fakeClientSecret123" not in result

    def test_refresh_token_assignment_redacted(self):
        raw = 'refresh_token: "1//FakeRefreshTokenZZZ"'
        result = redact_text(raw)
        assert "1//FakeRefreshTokenZZZ" not in result

    def test_id_token_assignment_redacted(self):
        raw = "id_token=eyJhbGciOiJSUzI1NiJ9.fake.sig"
        result = redact_text(raw)
        assert "eyJhbGciOiJSUzI1NiJ9.fake.sig" not in result


# =============================================================================
# Phone number masking
# =============================================================================

class TestPhoneRedaction:
    def test_german_plus49_masked(self):
        raw = "caller is +491234567890"
        result = redact_text(raw)
        assert "+491234567890" not in result
        assert "******" in result
        # Last 4 digits preserved in the masked form
        assert "7890" in result

    def test_german_national_0_prefix_masked(self):
        raw = "number: 0661123456789"
        result = redact_text(raw)
        assert "0661123456789" not in result
        assert "******" in result

    def test_german_0049_prefix_masked(self):
        raw = "dialling 0049301234567890"
        result = redact_text(raw)
        assert "0049301234567890" not in result
        assert "******" in result

    def test_raw_number_never_in_output(self):
        number = "+49301234567890"
        result = redact_text(f"outbound call to {number} initiated")
        assert number not in result

    def test_last_four_digits_preserved(self):
        result = redact_text("call +491751239999")
        # 9999 should appear in the masked representation
        assert "9999" in result

    def test_very_short_digit_sequence_not_masked(self):
        # 4-digit codes are not phone numbers — must remain untouched
        raw = "PIN: 1234"
        assert "1234" in redact_text(raw)


# =============================================================================
# Recursive dict / list redaction
# =============================================================================

class TestRecursiveRedaction:
    def test_flat_dict_values_redacted(self):
        data = {"bearer": "Bearer eyJfaketoken", "email": "test@test.com"}
        result = _redact_value(data)
        assert "eyJfaketoken" not in str(result)
        assert "test@test.com" not in str(result)

    def test_nested_dict_redacted(self):
        data = {"outer": {"api_key": "sk-or-v1-abc123def456789012", "note": "text"}}
        result = _redact_value(data)
        assert "sk-or-v1-abc123def456789012" not in str(result)
        assert "text" in str(result)

    def test_list_of_strings_redacted(self):
        data = ["user@example.com", "normal text", "+4912345678901"]
        result = _redact_value(data)
        assert "user@example.com" not in str(result)
        assert "+4912345678901" not in str(result)
        assert "normal text" in str(result)

    def test_list_of_dicts_redacted(self):
        data = [{"from": "alice@test.com"}, {"auth": "Bearer eyJx"}]
        result = _redact_value(data)
        assert "alice@test.com" not in str(result)
        assert "eyJx" not in str(result)

    def test_non_string_scalar_values_pass_through(self):
        data = {"count": 42, "flag": True, "ratio": 3.14}
        result = _redact_value(data)
        assert result["count"] == 42
        assert result["flag"] is True
        assert result["ratio"] == 3.14

    def test_empty_dict_unchanged(self):
        assert _redact_value({}) == {}

    def test_empty_list_unchanged(self):
        assert _redact_value([]) == []

    def test_deeply_nested_structure(self):
        data = {"level1": {"level2": {"email": "deep@nested.com"}}}
        result = _redact_value(data)
        assert "deep@nested.com" not in str(result)


# =============================================================================
# Edge cases and combined patterns
# =============================================================================

class TestEdgeCases:
    def test_empty_string_returns_empty(self):
        assert redact_text("") == ""

    def test_plain_text_is_unchanged(self):
        raw = "No sensitive data in this log line."
        assert redact_text(raw) == raw

    def test_idempotent_double_redaction(self):
        raw = "api_key: sk-or-v1-test123456789012"
        first_pass = redact_text(raw)
        second_pass = redact_text(first_pass)
        assert first_pass == second_pass

    def test_multiple_patterns_in_one_string(self):
        raw = (
            "user alice@example.com logged in with "
            "api_key=sk-or-v1-abc123def456 "
            "and Authorization: Bearer eyJfakeheader "
            "from +4912345678901"
        )
        result = redact_text(raw)
        assert "alice@example.com" not in result
        assert "sk-or-v1-abc123def456" not in result
        assert "eyJfakeheader" not in result
        assert "+4912345678901" not in result

    def test_number_not_in_other_context_words(self):
        # Verify that a number like "1234" in "version 1234" is not masked
        raw = "application version 1234 started"
        result = redact_text(raw)
        assert "1234" in result
