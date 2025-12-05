# Copyright (c) 2025, Sean McAvoy (@smcavoy) <seanmcavoy@gmail.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import patch

from ansible_collections.community.general.plugins.modules import lxd_storage_volume as module
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


class TestLXDStorageVolume(ModuleTestCase):
    def setUp(self):
        super().setUp()
        self.module = module

    def test_create_storage_volume(self):
        """A new storage volume is created when it does not exist."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {"type": "error", "error_code": 404},
            ("POST", "/1.0/storage-pools/default/volumes/custom"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args({"name": "test-vol", "pool": "default"}):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert result["old_state"] == "absent"
        assert "create" in result["actions"]

    def test_create_storage_volume_with_config(self):
        """A storage volume is created with config options."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {"type": "error", "error_code": 404},
            ("POST", "/1.0/storage-pools/default/volumes/custom"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "config": {"size": "10GiB"},
                            "description": "Test volume",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "create" in result["actions"]

    def test_create_block_volume(self):
        """A block storage volume can be created."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {"type": "error", "error_code": 404},
            ("POST", "/1.0/storage-pools/default/volumes/custom"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "content_type": "block",
                            "config": {"size": "20GiB"},
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "create" in result["actions"]

    def test_existing_volume_no_change(self):
        """An existing volume with matching config reports no change."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {
                "type": "sync",
                "metadata": {
                    "name": "test-vol",
                    "type": "custom",
                    "config": {"size": "10GiB"},
                    "description": "Test volume",
                },
            },
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "config": {"size": "10GiB"},
                            "description": "Test volume",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is False
        assert result["old_state"] == "present"
        assert result["actions"] == []

    def test_update_volume_description(self):
        """Updating a volume description triggers apply_configs."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {
                "type": "sync",
                "metadata": {
                    "name": "test-vol",
                    "type": "custom",
                    "description": "Old description",
                },
            },
            ("PUT", "/1.0/storage-pools/default/volumes/custom/test-vol"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "description": "New description",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "apply_configs" in result["actions"]

    def test_update_volume_size(self):
        """Updating volume size triggers apply_configs."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {
                "type": "sync",
                "metadata": {
                    "name": "test-vol",
                    "type": "custom",
                    "config": {"size": "10GiB"},
                },
            },
            ("PUT", "/1.0/storage-pools/default/volumes/custom/test-vol"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "config": {"size": "20GiB"},
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "apply_configs" in result["actions"]

    def test_delete_storage_volume(self):
        """An existing volume is deleted when state=absent."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {
                "type": "sync",
                "metadata": {"name": "test-vol", "type": "custom"},
            },
            ("DELETE", "/1.0/storage-pools/default/volumes/custom/test-vol"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args({"name": "test-vol", "pool": "default", "state": "absent"}):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert result["old_state"] == "present"
        assert "delete" in result["actions"]

    def test_delete_nonexistent_volume_no_change(self):
        """Deleting a non-existent volume reports no change."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {"type": "error", "error_code": 404},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args({"name": "test-vol", "pool": "default", "state": "absent"}):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is False
        assert result["old_state"] == "absent"
        assert result["actions"] == []

    def test_check_mode_create(self):
        """Check mode does not actually create the volume."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {"type": "error", "error_code": 404},
            # No POST response needed - check mode should not make the call
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "_ansible_check_mode": True,
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "create" in result["actions"]

    def test_check_mode_delete(self):
        """Check mode does not actually delete the volume."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {
                "type": "sync",
                "metadata": {"name": "test-vol", "type": "custom"},
            },
            # No DELETE response needed - check mode should not make the call
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "state": "absent",
                            "_ansible_check_mode": True,
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "delete" in result["actions"]

    def test_create_volume_with_project(self):
        """A volume can be created in a specific project."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol?project=myproject"): {
                "type": "error",
                "error_code": 404,
            },
            ("POST", "/1.0/storage-pools/default/volumes/custom?project=myproject"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "project": "myproject",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "create" in result["actions"]

    def test_create_volume_with_target(self):
        """A volume can be created on a specific cluster target."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {"type": "error", "error_code": 404},
            ("POST", "/1.0/storage-pools/default/volumes/custom?target=node01"): {"type": "sync", "metadata": {}},
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "target": "node01",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "create" in result["actions"]

    def test_migrate_volume_with_allow_migrate(self):
        """A volume is migrated when target differs and allow_migrate is true."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {
                "type": "sync",
                "metadata": {
                    "name": "test-vol",
                    "type": "custom",
                    "location": "node01",
                },
            },
            ("POST", "/1.0/storage-pools/default/volumes/custom/test-vol?target=node02"): {
                "type": "sync",
                "metadata": {},
            },
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "target": "node02",
                            "allow_migrate": True,
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "migrate" in result["actions"]

    def test_migrate_volume_fails_without_allow_migrate(self):
        """Migration fails when target differs and allow_migrate is false."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {
                "type": "sync",
                "metadata": {
                    "name": "test-vol",
                    "type": "custom",
                    "location": "node01",
                },
            },
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleFailJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "target": "node02",
                            "allow_migrate": False,
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert "allow_migrate=true" in result["msg"]
        assert "node01" in result["msg"]
        assert "node02" in result["msg"]

    def test_no_migration_when_target_matches_location(self):
        """No migration when target matches current location."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {
                "type": "sync",
                "metadata": {
                    "name": "test-vol",
                    "type": "custom",
                    "location": "node01",
                },
            },
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "target": "node01",
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is False
        assert "migrate" not in result["actions"]

    def test_check_mode_migrate(self):
        """Check mode does not actually migrate the volume."""
        FakeLXDClient.responses = {
            ("GET", "/1.0/storage-pools/default/volumes/custom/test-vol"): {
                "type": "sync",
                "metadata": {
                    "name": "test-vol",
                    "type": "custom",
                    "location": "node01",
                },
            },
            # No POST response needed - check mode should not make the call
        }

        with patch.object(self.module, "LXDClient", FakeLXDClient):
            with patch.object(self.module.os.path, "exists", return_value=False):
                with self.assertRaises(AnsibleExitJson) as exc:
                    with set_module_args(
                        {
                            "name": "test-vol",
                            "pool": "default",
                            "target": "node02",
                            "allow_migrate": True,
                            "_ansible_check_mode": True,
                        }
                    ):
                        self.module.main()

        result = exc.exception.args[0]
        assert result["changed"] is True
        assert "migrate" in result["actions"]
