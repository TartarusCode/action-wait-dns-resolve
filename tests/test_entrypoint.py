import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import dns.exception
import dns.resolver

import entrypoint


class ValidateHostnameTests(unittest.TestCase):
    def test_validate_hostname_rejects_whitespace_and_control_characters(self) -> None:
        with self.assertRaisesRegex(ValueError, "whitespace or control characters"):
            entrypoint.validate_hostname("bad host")

    def test_validate_hostname_normalizes_trailing_dot(self) -> None:
        self.assertEqual(entrypoint.validate_hostname("example.com."), "example.com")


class ValidateRecordTypeTests(unittest.TestCase):
    def test_validate_record_type_normalizes_case(self) -> None:
        self.assertEqual(entrypoint.validate_record_type("txt"), "TXT")


class ValidateMaxTimeTests(unittest.TestCase):
    def test_validate_max_time_rejects_zero(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 1 second"):
            entrypoint.validate_max_time("0")


class SetOutputTests(unittest.TestCase):
    def test_set_output_writes_github_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "github-output.txt"
            with patch.dict("os.environ", {"GITHUB_OUTPUT": str(output_path)}, clear=False):
                entrypoint.set_output("myOutput", "hello")

            output_contents = output_path.read_text(encoding="utf-8")
            self.assertIn("myOutput<<EOF_", output_contents)
            self.assertIn("\nhello\n", output_contents)


class ResolveDnsTests(unittest.TestCase):
    @patch("entrypoint.time.sleep", return_value=None)
    @patch("entrypoint.time.monotonic", side_effect=[0.0, 0.5])
    @patch("entrypoint.build_resolver")
    def test_resolve_dns_retries_and_returns_answers(
        self,
        mock_build_resolver: MagicMock,
        _mock_monotonic: MagicMock,
        _mock_sleep: MagicMock,
    ) -> None:
        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = [
            dns.resolver.NoAnswer(),
            ["1.2.3.4"],
        ]
        mock_build_resolver.return_value = mock_resolver

        result = entrypoint.resolve_dns("example.com", "A", 5.0)

        self.assertEqual(result, ["1.2.3.4"])
        self.assertEqual(mock_resolver.resolve.call_count, 2)
        mock_build_resolver.assert_called_once_with(5.0)

    @patch("entrypoint.time.sleep", return_value=None)
    @patch("entrypoint.time.monotonic", side_effect=[0.0, 1.1])
    @patch("entrypoint.build_resolver")
    def test_resolve_dns_times_out_when_deadline_expires(
        self,
        mock_build_resolver: MagicMock,
        _mock_monotonic: MagicMock,
        _mock_sleep: MagicMock,
    ) -> None:
        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = dns.exception.Timeout()
        mock_build_resolver.return_value = mock_resolver

        with self.assertRaisesRegex(TimeoutError, "Timed out after 1 seconds"):
            entrypoint.resolve_dns("example.com", "A", 1.0)


if __name__ == "__main__":
    unittest.main()
