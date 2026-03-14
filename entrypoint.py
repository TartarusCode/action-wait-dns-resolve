import ipaddress
import json
import logging
import math
import os
import time
import uuid

import dns.exception
import dns.name
import dns.resolver
from dns.exception import DNSException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_RECORD_TYPE = 'A'
DEFAULT_MAX_TIME = 60
SUPPORTED_RECORD_TYPES = {
    'A', 'AAAA', 'CNAME', 'MX', 'NS', 'PTR', 'SOA', 'SRV', 'TXT', 'SPF'
}
MAX_DNS_QUERY_TIME = 10.0
RETRYABLE_DNS_EXCEPTIONS = (
    dns.resolver.NXDOMAIN,
    dns.resolver.NoAnswer,
    dns.resolver.NoNameservers,
    dns.exception.Timeout,
)


def normalize_comparable_value(value: str) -> str:
    """Normalize DNS values for stable comparisons and JSON output."""
    return value.strip().rstrip(".").lower()


def validate_hostname(hostname: str) -> str:
    """
    Validate the hostname format.
    
    Args:
        hostname: The hostname to validate
        
    Returns:
        The validated hostname
        
    Raises:
        ValueError: If hostname is invalid
    """
    if not hostname or not hostname.strip():
        raise ValueError("Hostname cannot be empty")

    hostname = hostname.strip()
    if any(char in hostname for char in "\r\n\t\0 "):
        raise ValueError("Hostname cannot contain whitespace or control characters")

    normalized_hostname = hostname.rstrip(".")
    if not normalized_hostname:
        raise ValueError("Hostname cannot be empty")

    if len(normalized_hostname) > 253:
        raise ValueError("Hostname too long (max 253 characters)")

    try:
        parsed_hostname = dns.name.from_text(normalized_hostname)
    except DNSException as exc:
        raise ValueError(f"Invalid hostname: {exc}") from exc

    if any(len(label) > 63 for label in parsed_hostname.labels):
        raise ValueError("Hostname label too long (max 63 characters)")

    return normalized_hostname


def validate_record_type(record_type: str) -> str:
    """
    Validate the DNS record type.
    
    Args:
        record_type: The record type to validate
        
    Returns:
        The validated record type
        
    Raises:
        ValueError: If record type is not supported
    """
    normalized_record_type = record_type.strip().upper()
    if normalized_record_type not in SUPPORTED_RECORD_TYPES:
        error_msg = (
            f"Unsupported record type: {record_type}. "
            f"Supported types: {', '.join(sorted(SUPPORTED_RECORD_TYPES))}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    return normalized_record_type


def validate_max_time(max_time_str: str) -> float:
    """
    Validate and convert max time value.
    
    Args:
        max_time_str: Max time as string
        
    Returns:
        Max time as float
        
    Raises:
        ValueError: If max time is invalid
    """
    try:
        max_time = float(max_time_str) if max_time_str else float(DEFAULT_MAX_TIME)
        if not math.isfinite(max_time):
            raise ValueError("Max time must be a finite number")
        if max_time < 1:
            raise ValueError("Max time must be at least 1 second")
        if max_time > 3600:
            raise ValueError("Max time cannot exceed 3600 seconds")
        return max_time
    except ValueError as e:
        error_msg = f"Invalid max time value '{max_time_str}': {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def validate_nameservers(nameserver_str: str) -> list[str]:
    """Validate an optional comma-separated nameserver list."""
    if not nameserver_str or not nameserver_str.strip():
        return []

    validated_nameservers = []
    for raw_nameserver in nameserver_str.split(","):
        nameserver = raw_nameserver.strip()
        if not nameserver:
            continue
        try:
            validated_nameservers.append(str(ipaddress.ip_address(nameserver)))
        except ValueError as exc:
            raise ValueError(
                f"Invalid nameserver '{nameserver}'. Use IP addresses only."
            ) from exc

    if not validated_nameservers:
        raise ValueError("Nameserver input did not contain any valid IP addresses")

    return validated_nameservers


def validate_expected_value(expected_value: str) -> str | None:
    """Validate an optional expected DNS answer value."""
    if not expected_value or not expected_value.strip():
        return None

    validated_expected_value = expected_value.strip()
    if any(char in validated_expected_value for char in "\r\n\0"):
        raise ValueError("Expected value cannot contain control characters")

    return validated_expected_value


def set_output(name: str, value: str) -> None:
    """Write outputs using the GitHub Actions output file."""
    github_output_path = os.environ.get("GITHUB_OUTPUT")
    if not github_output_path:
        print(f"{name}={value}")
        return

    delimiter = f"EOF_{uuid.uuid4().hex}"
    with open(github_output_path, "a", encoding="utf-8") as github_output:
        github_output.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def build_resolver(max_time: float, nameservers: list[str] | None = None) -> dns.resolver.Resolver:
    """Create a resolver whose per-attempt timeout fits within the overall max time."""
    resolver = dns.resolver.Resolver()
    per_attempt_timeout = min(MAX_DNS_QUERY_TIME, max_time)
    resolver.timeout = per_attempt_timeout
    resolver.lifetime = per_attempt_timeout
    if nameservers:
        resolver.nameservers = nameservers
    return resolver


def assert_expected_value(resolved_answers: list[str], expected_value: str) -> bool:
    """Check whether any resolved value matches the expected value."""
    normalized_expected = normalize_comparable_value(expected_value)
    return any(
        normalize_comparable_value(answer) == normalized_expected
        for answer in resolved_answers
    )


def build_resolution_result(
    hostname: str,
    record_type: str,
    nameservers: list[str],
    resolved_values: list[str],
    expected_value: str | None,
    matched_expected: bool,
) -> str:
    """Create a structured JSON summary for downstream workflow consumers."""
    return json.dumps(
        {
            "hostname": hostname,
            "record_type": record_type,
            "nameservers": nameservers,
            "resolved_values": resolved_values,
            "expected_value": expected_value,
            "matched_expected": matched_expected,
        },
        separators=(",", ":"),
    )


def resolve_dns(
    hostname: str,
    record_type: str = DEFAULT_RECORD_TYPE,
    max_time: float = float(DEFAULT_MAX_TIME),
    nameservers: list[str] | None = None,
    expected_value: str | None = None,
) -> list[str]:
    """
    Resolve a DNS record with retry logic.
    
    Args:
        hostname: The hostname to resolve
        record_type: The DNS record type to resolve
        
    Raises:
        dns.resolver.NXDOMAIN: If domain does not exist
        dns.resolver.NoAnswer: If no answer found
        dns.resolver.Timeout: If resolution times out
        DNSException: For non-retryable DNS errors
    """
    if not math.isfinite(max_time):
        raise ValueError("Max time must be a finite number")

    resolver = build_resolver(max_time, nameservers)
    deadline = time.monotonic() + max_time
    attempt = 1
    retry_delay = 1.0

    while True:
        try:
            logger.info(f"Resolving {record_type} record for {hostname} (attempt {attempt})")
            answers = resolver.resolve(hostname, record_type)
            resolved_answers = [str(answer) for answer in answers]
            if expected_value and not assert_expected_value(resolved_answers, expected_value):
                raise dns.resolver.NoAnswer(
                    f"Resolved values {resolved_answers} did not match expected value '{expected_value}'"
                )
            logger.info(
                f"Successfully resolved {record_type} record for {hostname}: {resolved_answers}"
            )
            return resolved_answers
        except RETRYABLE_DNS_EXCEPTIONS as exc:
            remaining_time = deadline - time.monotonic()
            logger.warning(
                f"DNS resolution attempt {attempt} failed for {hostname} ({record_type}): {exc}"
            )
            if remaining_time <= 0:
                raise TimeoutError(
                    f"Timed out after {max_time:g} seconds waiting for {record_type} "
                    f"record for {hostname}"
                ) from exc

            sleep_time = min(retry_delay, remaining_time)
            logger.info(
                f"Retrying in {sleep_time:.1f} seconds ({remaining_time:.1f} seconds remaining)"
            )
            time.sleep(sleep_time)
            attempt += 1
            retry_delay = min(retry_delay * 2, MAX_DNS_QUERY_TIME)
        except DNSException as exc:
            logger.error(f"Non-retryable DNS error for {hostname} ({record_type}): {exc}")
            raise


def main() -> None:
    """Main function to handle DNS resolution with validation and error handling."""
    try:
        # Get and validate inputs
        hostname = os.environ["INPUT_REMOTEHOST"]
        record_type = os.environ.get("INPUT_RECORDTYPE", DEFAULT_RECORD_TYPE)
        nameserver_str = os.environ.get("INPUT_NAMESERVER", "")
        expected_value_str = os.environ.get("INPUT_EXPECTEDVALUE", "")
        max_time_str = os.environ.get("INPUT_MAXTIME", str(DEFAULT_MAX_TIME))

        # Validate inputs
        validated_hostname = validate_hostname(hostname)
        validated_record_type = validate_record_type(record_type)
        validated_nameservers = validate_nameservers(nameserver_str)
        validated_expected_value = validate_expected_value(expected_value_str)
        validated_max_time = validate_max_time(max_time_str)

        logger.info(
            f"Starting DNS resolution: {validated_hostname} ({validated_record_type})"
        )

        # Attempt resolution
        resolved_values = resolve_dns(
            validated_hostname,
            validated_record_type,
            validated_max_time,
            validated_nameservers,
            validated_expected_value,
        )

        output_message = f"Successfully resolved {validated_record_type} record for {validated_hostname}"
        matched_expected = validated_expected_value is not None
        set_output("message", output_message)
        set_output("error_message", "")
        set_output("resolved_values", json.dumps(resolved_values))
        set_output("matched_expected", str(matched_expected).lower())
        set_output(
            "resolution_result",
            build_resolution_result(
                validated_hostname,
                validated_record_type,
                validated_nameservers,
                resolved_values,
                validated_expected_value,
                matched_expected,
            ),
        )
        logger.info("DNS resolution completed successfully")

    except TimeoutError as exc:
        error_msg = str(exc)
        logger.error(error_msg)
        set_output("error_message", error_msg)
        set_output("resolved_values", "[]")
        set_output("matched_expected", "false")
        set_output("resolution_result", "{}")
        raise RuntimeError(error_msg) from exc
    except ValueError as exc:
        error_msg = f"Invalid input: {str(exc)}"
        logger.error(error_msg)
        set_output("error_message", error_msg)
        set_output("resolved_values", "[]")
        set_output("matched_expected", "false")
        set_output("resolution_result", "{}")
        raise RuntimeError(error_msg) from exc
    except DNSException as exc:
        error_msg = f"DNS resolution failed: {str(exc)}"
        logger.error(error_msg)
        set_output("error_message", error_msg)
        set_output("resolved_values", "[]")
        set_output("matched_expected", "false")
        set_output("resolution_result", "{}")
        raise RuntimeError(error_msg) from exc
    except Exception as exc:
        error_msg = f"Unexpected error: {str(exc)}"
        logger.error(error_msg)
        set_output("error_message", error_msg)
        set_output("resolved_values", "[]")
        set_output("matched_expected", "false")
        set_output("resolution_result", "{}")
        raise


if __name__ == "__main__":
    main()
