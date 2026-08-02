import unittest

from utils.sentry_config import (
    DEFAULT_SENTRY_TRACES_SAMPLE_RATE,
    parse_sentry_sample_rate,
    parse_sentry_send_default_pii,
)


class SentryConfigTests(unittest.TestCase):
    def test_pii_is_disabled_by_default_and_on_malformed_values(self):
        self.assertFalse(parse_sentry_send_default_pii(None))
        self.assertFalse(parse_sentry_send_default_pii("false"))
        self.assertFalse(parse_sentry_send_default_pii("unexpected"))

    def test_pii_requires_an_explicit_truthy_value(self):
        for value in ("true", "1", "yes", "on", " TRUE "):
            with self.subTest(value=value):
                self.assertTrue(parse_sentry_send_default_pii(value))

    def test_trace_sampling_uses_a_low_safe_default(self):
        self.assertEqual(
            parse_sentry_sample_rate(None), DEFAULT_SENTRY_TRACES_SAMPLE_RATE
        )
        self.assertEqual(
            parse_sentry_sample_rate("bad"), DEFAULT_SENTRY_TRACES_SAMPLE_RATE
        )
        self.assertEqual(
            parse_sentry_sample_rate("nan"), DEFAULT_SENTRY_TRACES_SAMPLE_RATE
        )

    def test_trace_sampling_is_clamped(self):
        self.assertEqual(parse_sentry_sample_rate("-1"), 0.0)
        self.assertEqual(parse_sentry_sample_rate("0.25"), 0.25)
        self.assertEqual(parse_sentry_sample_rate("2"), 1.0)


if __name__ == "__main__":
    unittest.main()
