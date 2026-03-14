# action-wait-dns-resolve

GitHub Action to wait for DNS records to resolve with retry logic and comprehensive error handling.

[![Github Action - Wait DNS](https://github.com/BGarber42/action-wait-dns-resolve/actions/workflows/main.yml/badge.svg)](https://github.com/BGarber42/action-wait-dns-resolve/actions/workflows/main.yml)

## Features

- **DNS Resolution**: Wait for DNS records to resolve with automatic retry logic
- **Multiple Record Types**: Support for A, AAAA, CNAME, MX, NS, PTR, SOA, SRV, TXT, SPF records
- **Custom DNS Servers**: Query specific resolver IPs when you need to verify propagation against a chosen nameserver
- **Expected Value Assertions**: Retry until a specific DNS answer appears instead of stopping at the first successful response
- **Structured Outputs**: Export resolved values and a machine-readable JSON result for downstream workflow logic
- **Current Runtime**: Runs on a pinned `python:3.14-alpine` container base
- **Comprehensive Validation**: Input validation for hostnames, record types, and timeouts
- **Detailed Error Handling**: Specific error messages for different failure scenarios
- **Configurable Timeouts**: Customizable maximum wait time
- **Structured Logging**: Detailed logging for debugging and monitoring

## Usage

Pin this action to a full commit SHA in production workflows for supply-chain safety, and set `permissions: contents: read` when the workflow does not need broader token access.

### Basic Usage

```yaml
- name: Wait for DNS Resolution
  uses: BGarber42/action-wait-dns-resolve@<full-commit-sha>
  with:
    remotehost: 'example.com'
    recordtype: 'A'
    maxtime: '60'
```

### Custom DNS Server and Expected Value

```yaml
- name: Wait for DNS Cutover
  id: dns_check
  uses: BGarber42/action-wait-dns-resolve@<full-commit-sha>
  with:
    remotehost: 'api.example.com'
    recordtype: 'CNAME'
    nameserver: '1.1.1.1,8.8.8.8'
    expectedvalue: 'new-target.example.net'
    maxtime: '180'
```

### Advanced Usage

```yaml
permissions:
  contents: read

steps:
  - name: Wait for Multiple DNS Records
    id: dns_check
    uses: BGarber42/action-wait-dns-resolve@<full-commit-sha>
    with:
      remotehost: 'api.example.com'
      recordtype: 'CNAME'
      maxtime: '120'

  - name: Check DNS Result
    env:
      DNS_STATUS: ${{ steps.dns_check.outputs.message }}
      DNS_VALUES: ${{ steps.dns_check.outputs.resolved_values }}
      DNS_RESULT: ${{ steps.dns_check.outputs.resolution_result }}
    run: printf 'DNS Status: %s\n' "$DNS_STATUS"
  - name: Show Structured DNS Result
    env:
      DNS_VALUES: ${{ steps.dns_check.outputs.resolved_values }}
      DNS_RESULT: ${{ steps.dns_check.outputs.resolution_result }}
    run: |
      printf 'Resolved Values: %s\n' "$DNS_VALUES"
      printf 'Structured Result: %s\n' "$DNS_RESULT"
```

### Wait for New Domain

```yaml
- name: Wait for New Domain to Propagate
  uses: BGarber42/action-wait-dns-resolve@<full-commit-sha>
  with:
    remotehost: 'new-domain.com'
    recordtype: 'A'
    maxtime: '300'  # 5 minutes
```

## Inputs

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `remotehost` | Hostname to resolve (e.g., example.com) | Yes | None |
| `recordtype` | DNS record type to resolve | No | `A` |
| `nameserver` | Optional resolver IP, or comma-separated resolver IPs, to query instead of the system resolver | No | Empty |
| `expectedvalue` | Optional expected DNS answer value. The action retries until one resolved answer matches it. | No | Empty |
| `maxtime` | Maximum time in seconds to wait (1-3600) | No | `60` |

## Outputs

| Parameter | Description |
|-----------|-------------|
| `message` | Success message when DNS resolution succeeds |
| `error_message` | Error message written before the step fails |
| `resolved_values` | JSON array of resolved answer strings |
| `matched_expected` | `true` when `expectedvalue` was provided and matched before timeout, otherwise `false` |
| `resolution_result` | JSON object containing the hostname, record type, nameservers, resolved values, expected value, and match result |

## Supported Record Types

- **A**: IPv4 address records
- **AAAA**: IPv6 address records
- **CNAME**: Canonical name records
- **MX**: Mail exchange records
- **NS**: Name server records
- **PTR**: Pointer records
- **SOA**: Start of authority records
- **SRV**: Service records
- **TXT**: Text records
- **SPF**: Sender Policy Framework records

## Error Handling

The action handles various DNS resolution scenarios:

- **NXDOMAIN**: Domain does not exist
- **NoAnswer**: No DNS answer found
- **Timeout**: DNS resolution times out
- **Invalid Inputs**: Invalid hostname, record type, or timeout values
- **Network Issues**: Connection problems

The action writes outputs through `$GITHUB_OUTPUT`, so `steps.<id>.outputs.message`, `steps.<id>.outputs.error_message`, `steps.<id>.outputs.resolved_values`, `steps.<id>.outputs.matched_expected`, and `steps.<id>.outputs.resolution_result` are available to later steps.

## Runtime

This action runs as a Docker-based action on a pinned `python:3.14-alpine` image digest. Pinning the base image keeps builds reproducible while using a current Python runtime with a longer support horizon.

## Best Practices

1. **Use Appropriate Timeouts**: Set reasonable timeouts based on your DNS propagation expectations
2. **Handle Errors**: Check the error output in your workflows
3. **Use Environment Variables for Outputs**: Pass action outputs through `env:` before referencing them in shell commands
4. **Prefer Explicit Nameservers for Cutovers**: Set `nameserver` when you need to verify propagation against a specific resolver
5. **Use `expectedvalue` for Deterministic Checks**: Assert the exact DNS answer you expect instead of only checking for any response
6. **Validate Hostnames**: Ensure hostnames are properly formatted
7. **Monitor Logs**: Use structured logging for debugging
8. **Test Different Record Types**: Verify the specific record type you need

## Development

Run the unit test suite locally with:

```bash
python -m unittest discover -s tests -v
```

## Common Use Cases

### Wait for Domain Propagation

```yaml
- name: Wait for Domain to Propagate
  uses: BGarber42/action-wait-dns-resolve@<full-commit-sha>
  with:
    remotehost: 'new-domain.com'
    recordtype: 'A'
    maxtime: '600'  # 10 minutes
```

### Verify Load Balancer DNS

```yaml
- name: Verify Load Balancer DNS
  uses: BGarber42/action-wait-dns-resolve@<full-commit-sha>
  with:
    remotehost: 'lb.example.com'
    recordtype: 'CNAME'
    maxtime: '120'
```

### Wait for a Specific DNS Target

```yaml
- name: Wait for DNS Target to Match
  uses: BGarber42/action-wait-dns-resolve@<full-commit-sha>
  with:
    remotehost: 'api.example.com'
    recordtype: 'CNAME'
    nameserver: '1.1.1.1'
    expectedvalue: 'new-target.example.net'
    maxtime: '300'
```

### Check Mail Server Records

```yaml
- name: Check Mail Server Records
  uses: BGarber42/action-wait-dns-resolve@<full-commit-sha>
  with:
    remotehost: 'example.com'
    recordtype: 'MX'
    maxtime: '60'
```

## Troubleshooting

### Common Issues

1. **Timeout Errors**: Increase the maxtime parameter for slow DNS propagation
2. **Invalid Hostname**: Ensure hostnames are properly formatted
3. **Unsupported Record Type**: Use only supported record types
4. **Network Issues**: Check network connectivity and DNS server availability

### Debugging

Enable debug logging by setting the `ACTIONS_STEP_DEBUG` secret to `true` in your repository.
