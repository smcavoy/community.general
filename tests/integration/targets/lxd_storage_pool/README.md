# LXD Storage Integration Tests

This directory contains integration tests for the `lxd_storage_pool` module.

## Requirements

- LXD must be installed and initialized
- Sufficient permissions to manage LXD storage
- At least 5GB of free disk space for test storage pools

## Running Tests

### Using ansible-test

```bash
ansible-test integration lxd_storage_pool --docker
```

### Manual Testing

```bash
ansible-playbook tasks/main.yml
```

## Test Coverage

The integration tests verify:

1. **Check Mode**: Ensures check mode correctly previews changes without applying them
2. **Pool Creation**: Tests creating storage pools with various drivers
3. **Pool Updates**: Tests updating pool configurations and descriptions
4. **Pool Idempotency**: Verifies unchanged pools don't trigger updates
5. **Volume Creation**: Tests creating custom storage volumes
6. **Volume Updates**: Tests updating volume configurations (size, description)
7. **Volume Idempotency**: Verifies unchanged volumes don't trigger updates
8. **Volume Deletion**: Tests deleting storage volumes
9. **Pool Deletion**: Tests deleting storage pools
10. **Deletion Idempotency**: Verifies deleting non-existent resources is idempotent

## Test Scenarios

- Directory-based storage pools (simplest, works everywhere)
- Custom storage volumes with size configuration
- Check mode operations
- Idempotent operations
- Update operations
- Cleanup and deletion

## Notes

- Tests use the snap socket path by default (`unix:/var/snap/lxd/common/lxd/unix.socket`)
- Tests create temporary resources prefixed with `integration-test-`
- All test resources are cleaned up after successful test runs
- Tests require root/sudo access to interact with LXD
