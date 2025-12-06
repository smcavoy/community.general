<!--
SPDX-FileCopyrightText: 2025 Sean McAvoy <seanmcavoy@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later
-->

# LXD Storage Volume Integration Tests

This directory contains integration tests for the `lxd_storage_volume` module.

## Requirements

- LXD must be installed and initialized
- Sufficient permissions to manage LXD storage
- At least 5GB of free disk space for test storage volumes

## Running Tests

### Using ansible-test

```bash
ansible-test integration lxd_storage_volume --docker
```

### Manual Testing

```bash
ansible-playbook tasks/main.yml
```

## Test Coverage

The integration tests verify:

1. **Check Mode**: Ensures check mode correctly previews changes without applying them
2. **Filesystem Volume Creation**: Tests creating filesystem-type custom storage volumes
3. **Filesystem Volume Updates**: Tests updating volume configurations (size, description)
4. **Filesystem Volume Idempotency**: Verifies unchanged volumes don't trigger updates
5. **Block Volume Creation**: Tests creating block-type custom storage volumes
6. **Block Volume Idempotency**: Verifies unchanged block volumes don't trigger updates
7. **Volume Deletion**: Tests deleting storage volumes
8. **Volume Migration** (cluster only): Tests migrating volumes between cluster members
   - Creating volumes on specific cluster nodes
   - Blocking migration when `allow_migrate=false`
   - Allowing migration when `allow_migrate=true`
   - Migration idempotency
   - Migration check mode

## Test Scenarios

- Filesystem-based custom volumes
- Block-based custom volumes
- Volume size configuration and updates
- Check mode operations
- Idempotent operations
- Cleanup and deletion

## Notes

- Tests use the snap socket path by default (`unix:/var/snap/lxd/common/lxd/unix.socket`)
- Tests create temporary resources prefixed with `test-` or `integration-test-`
- All test resources are cleaned up after successful test runs
- Tests require root/sudo access to interact with LXD
- Migration tests only run when LXD is configured as a cluster with 2+ nodes
- Migration tests are automatically skipped on non-clustered LXD installations
