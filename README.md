# action-wait-dns-resolve

GitHub Action to wait for DNS records to resolve with retry logic and comprehensive error handling.

[![Github Action - Wait DNS](https://github.com/BGarber42/action-wait-dns-resolve/actions/workflows/main.yml/badge.svg)](https://github.com/BGarber42/action-wait-dns-resolve/actions/workflows/main.yml)

## Features

- **DNS Resolution**: Wait for DNS records to resolve with automatic retry logic
- **Multiple Record Types**: Support for A, AAAA, CNAME, MX, NS, PTR, SOA, SRV, TXT, SPF records
- **Comprehensive Validation**: Input validation for hostnames, record types, and timeouts
- **Detailed Error Handling**: Specific error messages for different failure scenarios
- **Configurable Timeouts**: Customizable maximum wait time
- **Structured Logging**: Detailed logging for debugging and monitoring

## Usage

### Basic Usage

```yaml
- name: Wait for DNS Resolution
  uses: BGarber42/action-wait-dns-resolve@main
  with:
    remotehost: 'example.com'
    recordtype: 'A'
    maxtime: '60'
```

### Advanced Usage

```yaml
- name: Wait for Multiple DNS Records
  uses: BGarber42/action-wait-dns-resolve@main
  with:
    remotehost: 'api.example.com'
    recordtype: 'CNAME'
    maxtime: '120'
  id: dns_check
  
- name: Check DNS Result
  run: |
    echo "DNS Status: ${{ steps.dns_check.outputs.myOutput }}"
```

### Wait for New Domain

```yaml
- name: Wait for New Domain to Propagate
  uses: BGarber42/action-wait-dns-resolve@main
  with:
    remotehost: 'new-domain.com'
    recordtype: 'A'
    maxtime: '300'  # 5 minutes
```

## Inputs

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `remotehost` | Hostname to resolve (e.g., example.com) | Yes | `google.com` |
| `recordtype` | DNS record type to resolve | No | `A` |
| `maxtime` | Maximum time in seconds to wait (1-3600) | No | `60` |

## Outputs

| Parameter | Description |
|-----------|-------------|
| `myOutput` | Success message when DNS resolution succeeds |
| `error` | Error message if DNS resolution fails |

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

## Best Practices

1. **Use Appropriate Timeouts**: Set reasonable timeouts based on your DNS propagation expectations
2. **Handle Errors**: Check the error output in your workflows
3. **Validate Hostnames**: Ensure hostnames are properly formatted
4. **Monitor Logs**: Use structured logging for debugging
5. **Test Different Record Types**: Verify the specific record type you need

## Common Use Cases

### Wait for Domain Propagation

```yaml
- name: Wait for Domain to Propagate
  uses: BGarber42/action-wait-dns-resolve@main
  with:
    remotehost: 'new-domain.com'
    recordtype: 'A'
    maxtime: '600'  # 10 minutes
```

### Verify Load Balancer DNS

```yaml
- name: Verify Load Balancer DNS
  uses: BGarber42/action-wait-dns-resolve@main
  with:
    remotehost: 'lb.example.com'
    recordtype: 'CNAME'
    maxtime: '120'
```

### Check Mail Server Records

```yaml
- name: Check Mail Server Records
  uses: BGarber42/action-wait-dns-resolve@main
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
