import os
import logging
from typing import Optional

import backoff
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

resolver = dns.resolver.Resolver()


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
    if len(hostname) > 253:
        raise ValueError("Hostname too long (max 253 characters)")
    
    return hostname


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
    if record_type not in SUPPORTED_RECORD_TYPES:
        error_msg = f"Unsupported record type: {record_type}. Supported types: {', '.join(SUPPORTED_RECORD_TYPES)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return record_type


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
        max_time = float(max_time_str) if max_time_str else DEFAULT_MAX_TIME
        if max_time <= 0:
            raise ValueError("Max time must be greater than 0")
        if max_time > 3600:  # 1 hour max
            raise ValueError("Max time cannot exceed 3600 seconds")
        return max_time
    except ValueError as e:
        error_msg = f"Invalid max time value '{max_time_str}': {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)


@backoff.on_exception(
    backoff.expo, 
    (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout),
    max_time=lambda: float(os.environ.get("INPUT_MAXTIME", str(DEFAULT_MAX_TIME)))
)
def resolve_dns(hostname: str, record_type: str = DEFAULT_RECORD_TYPE) -> None:
    """
    Resolve a DNS record with retry logic.
    
    Args:
        hostname: The hostname to resolve
        record_type: The DNS record type to resolve
        
    Raises:
        dns.resolver.NXDOMAIN: If domain does not exist
        dns.resolver.NoAnswer: If no answer found
        dns.resolver.Timeout: If resolution times out
        DNSException: For other DNS errors
    """
    try:
        logger.info(f"Resolving {record_type} record for {hostname}")
        answers = resolver.resolve(hostname, record_type)
        logger.info(f"Successfully resolved {record_type} record for {hostname}: {[str(answer) for answer in answers]}")
    except DNSException as e:
        logger.warning(f"DNS resolution failed for {hostname} ({record_type}): {str(e)}")
        raise


def main() -> None:
    """Main function to handle DNS resolution with validation and error handling."""
    try:
        # Configure backoff logging
        logging.getLogger("backoff").addHandler(logging.StreamHandler())
        
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
        resolve_dns(validated_hostname, validated_record_type)
        
        # Use new GitHub Actions output syntax
        output_message = f"Successfully resolved {validated_record_type} record for {validated_hostname}"
        print(f"myOutput={output_message}")
        logger.info("DNS resolution completed successfully")
        
    except TimeoutError:
        error_msg = "Timed out waiting for DNS resolution"
        logger.error(error_msg)
        print(f"error={error_msg}")
        raise Exception(error_msg)
    except ValueError as e:
        error_msg = f"Invalid input: {str(e)}"
        logger.error(error_msg)
        print(f"error={error_msg}")
        raise Exception(error_msg)
    except DNSException as e:
        error_msg = f"DNS resolution failed: {str(e)}"
        logger.error(error_msg)
        print(f"error={error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        print(f"error={error_msg}")
        raise


if __name__ == "__main__":
    main()
