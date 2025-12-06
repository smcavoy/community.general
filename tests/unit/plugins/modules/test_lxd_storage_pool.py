# Copyright (c) 2025, Sean McAvoy (@smcavoy) <seanmcavoy@gmail.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import patch

from ansible_collections.community.general.plugins.modules import lxd_storage_pool as module
from ansible_collections.community.internal_test_tools.tests.unit.plugins.modules.utils import (
    AnsibleExitJson,
    AnsibleFailJson,
    ModuleTestCase,
    set_module_args,
)


class FakeLXDClient:
    responses: dict[tuple[str, str], dict] = {}

    def __init__(self, url, key_file=None, cert_file=None, debug=False, **kwargs):
        self.url = url
        self.key_file = key_file
        self.cert_file = cert_file
        self.debug = debug
        self.logs = [{"type": "fake-request"}] if debug else []

    def authenticate(self, trust_password):
        self.trust_password = trust_password

    def do(self, method, url, body_json=None, ok_error_codes=None, **kwargs):
        try:
            return self.responses[(method, url)]
        except KeyError as exc:
            raise AssertionError(f"Unexpected call: {method} {url}") from exc


class TestLXDStoragePool(ModuleTestCase):
    def setUp(self):
        super().setUp()
        self.module = module

    def test_create_storage_pool(self):
        """A new storage pool is created when it does not exist."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {"type": "error", "error_code": 404},
            ("POST", "/1.0/storage-pools"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args({"name": "test-pool", "driver": "dir"}):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert result["old_state"] == "absent"
        assert "create" in result["actions"]

    def test_create_storage_pool_with_config(self):
        """A storage pool is created with config options."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {"type": "error", "error_code": 404},
            ("POST", "/1.0/storage-pools"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-pool",
                            "driver": "dir",
                            "config": {"source": "/var/lib/lxd/storage-pools/test-pool"},
                            "description": "Test pool",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "create" in result["actions"]

    def test_create_storage_pool_fails_without_driver(self):
        """Creating a pool without a driver fails."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {"type": "error", "error_code": 404},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleFailJson) as exc:
                    with set_module_args({"name": "test-pool"}):
                        self.module.main()

        result = exc.exception.args[0]
        assert "driver is required" in result["msg"]

    def test_existing_pool_no_change(self):
        """An existing pool with matching config reports no change."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {
                "type": "sync",
                "metadata": {
                    "name": "test-pool",
                    "driver": "dir",
                    "config": {"source": "/var/lib/lxd/storage-pools/test-pool"},
                    "description": "Test pool",
                },
            },
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-pool",
                            "driver": "dir",
                            "config": {"source": "/var/lib/lxd/storage-pools/test-pool"},
                            "description": "Test pool",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is False
        assert result["old_state"] == "present"
        assert result["actions"] == []

    def test_update_pool_description(self):
        """Updating a pool description triggers apply_configs."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {
                "type": "sync",
                "metadata": {
                    "name": "test-pool",
                    "driver": "dir",
                    "description": "Old description",
                },
            },
            ("PUT", "/1.0/storage-pools/test-pool"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-pool",
                            "description": "New description",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "apply_configs" in result["actions"]

    def test_update_pool_config(self):
        """Updating pool config triggers apply_configs."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {
                "type": "sync",
                "metadata": {
                    "name": "test-pool",
                    "driver": "zfs",
                    "config": {"size": "10GiB"},
                },
            },
            ("PUT", "/1.0/storage-pools/test-pool"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-pool",
                            "config": {"size": "20GiB"},
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "apply_configs" in result["actions"]

    def test_delete_storage_pool(self):
        """An existing pool is deleted when state=absent."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {
                "type": "sync",
                "metadata": {"name": "test-pool", "driver": "dir"},
            },
            ("DELETE", "/1.0/storage-pools/test-pool"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args({"name": "test-pool", "state": "absent"}):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert result["old_state"] == "present"
        assert "delete" in result["actions"]

    def test_delete_nonexistent_pool_no_change(self):
        """Deleting a non-existent pool reports no change."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {"type": "error", "error_code": 404},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args({"name": "test-pool", "state": "absent"}):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is False
        assert result["old_state"] == "absent"
        assert result["actions"] == []

    def test_check_mode_create(self):
        """Check mode does not actually create the pool."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {"type": "error", "error_code": 404},
            # No POST response needed - check mode should not make the call
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-pool",
                            "driver": "dir",
                            "_ansible_check_mode": True,
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "create" in result["actions"]

    def test_check_mode_delete(self):
        """Check mode does not actually delete the pool."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {
                "type": "sync",
                "metadata": {"name": "test-pool", "driver": "dir"},
            },
            # No DELETE response needed - check mode should not make the call
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-pool",
                            "state": "absent",
                            "_ansible_check_mode": True,
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "delete" in result["actions"]

    def test_create_pool_with_project(self):
        """A pool can be created in a specific project."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool?project=myproject"): {"type": "error", "error_code": 404},
            ("POST", "/1.0/storage-pools?project=myproject"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-pool",
                            "driver": "dir",
                            "project": "myproject",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "create" in result["actions"]

    def test_create_pool_with_target(self):
        """A pool can be created on a specific cluster target."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/test-pool"): {"type": "error", "error_code": 404},
            ("POST", "/1.0/storage-pools?target=node01"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-pool",
                            "driver": "dir",
                            "target": "node01",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "create" in result["actions"]
