import logging
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
        if max_time < 1:
            raise ValueError("Max time must be at least 1 second")
        if max_time > 3600:
            raise ValueError("Max time cannot exceed 3600 seconds")
        return max_time
    except ValueError as e:
        error_msg = f"Invalid max time value '{max_time_str}': {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def set_output(name: str, value: str) -> None:
    """Write outputs using the GitHub Actions output file."""
    github_output_path = os.environ.get("GITHUB_OUTPUT")
    if not github_output_path:
        print(f"{name}={value}")
        return

    delimiter = f"EOF_{uuid.uuid4().hex}"
    with open(github_output_path, "a", encoding="utf-8") as github_output:
        github_output.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def build_resolver(max_time: float) -> dns.resolver.Resolver:
    """Create a resolver whose per-attempt timeout fits within the overall max time."""
    resolver = dns.resolver.Resolver()
    per_attempt_timeout = min(MAX_DNS_QUERY_TIME, max_time)
    resolver.timeout = per_attempt_timeout
    resolver.lifetime = per_attempt_timeout
    return resolver


def resolve_dns(
    hostname: str,
    record_type: str = DEFAULT_RECORD_TYPE,
    max_time: float = float(DEFAULT_MAX_TIME),
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
    resolver = build_resolver(max_time)
    deadline = time.monotonic() + max_time
    attempt = 1
    retry_delay = 1.0

    while True:
        try:
            logger.info(f"Resolving {record_type} record for {hostname} (attempt {attempt})")
            answers = resolver.resolve(hostname, record_type)
            resolved_answers = [str(answer) for answer in answers]
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
        max_time_str = os.environ.get("INPUT_MAXTIME", str(DEFAULT_MAX_TIME))

        # Validate inputs
        validated_hostname = validate_hostname(hostname)
        validated_record_type = validate_record_type(record_type)
        validated_max_time = validate_max_time(max_time_str)

        logger.info(f"Starting DNS resolution: {validated_hostname} ({validated_record_type})")

        # Attempt resolution
        resolve_dns(validated_hostname, validated_record_type, validated_max_time)

        output_message = f"Successfully resolved {validated_record_type} record for {validated_hostname}"
        set_output("myOutput", output_message)
        set_output("error", "")
        logger.info("DNS resolution completed successfully")

    except TimeoutError as exc:
        error_msg = str(exc)
        logger.error(error_msg)
        set_output("error", error_msg)
        raise RuntimeError(error_msg) from exc
    except ValueError as exc:
        error_msg = f"Invalid input: {str(exc)}"
        logger.error(error_msg)
        set_output("error", error_msg)
        raise RuntimeError(error_msg) from exc
    except DNSException as exc:
        error_msg = f"DNS resolution failed: {str(exc)}"
        logger.error(error_msg)
        set_output("error", error_msg)
        raise RuntimeError(error_msg) from exc
    except Exception as exc:
        error_msg = f"Unexpected error: {str(exc)}"
        logger.error(error_msg)
        set_output("error", error_msg)
        raise


if __name__ == "__main__":
    main()
