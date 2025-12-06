#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2024, Sean McAvoy <seanmcavoy@gmail.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

__metaclass__ = type


DOCUMENTATION = """
---
module: lxd_storage_pool
short_description: Manage LXD storage pools
version_added: 12.1.0
description:
  - Manages LXD storage pools.
author: "Sean McAvoy (@smcavoy)"
extends_documentation_fragment:
  - community.general.attributes
attributes:
  check_mode:
    support: full
  diff_mode:
    support: full
options:
  name:
    description:
      - Name of the storage pool.
    type: str
    required: true
  project:
    description:
      - 'Project of the storage pool.
        See U(https://documentation.ubuntu.com/lxd/en/latest/projects/).'
    type: str
  driver:
    description:
      - 'Storage pool driver (required when creating a pool).
        See U(https://documentation.ubuntu.com/lxd/en/latest/reference/storage_drivers/).'
      - Common drivers include V(dir), V(zfs), V(btrfs), V(lvm), V(ceph).
    type: str
  config:
    description:
      - 'Configuration for the storage pool.
        See U(https://documentation.ubuntu.com/lxd/en/latest/api/).'
      - This can include driver-specific options like V(size), V(source), and so on.
    type: dict
  description:
    description:
      - Description of the storage pool.
    type: str
  state:
    choices:
      - present
      - absent
    description:
      - Define the state of the storage pool.
    default: present
    type: str
  target:
    description:
      - For cluster deployments. Will attempt to create a storage pool on a target node.
      - The name should match the node name you see in C(lxc cluster list).
    type: str
  url:
    description:
      - The unix domain socket path or the https URL for the LXD server.
    default: unix:/var/lib/lxd/unix.socket
    type: str
  snap_url:
    description:
      - The Unix domain socket path when LXD is installed by snap package manager.
    default: unix:/var/snap/lxd/common/lxd/unix.socket
    type: str
  client_key:
    description:
      - The client certificate key file path.
      - If not specified, it defaults to C(${HOME}/.config/lxc/client.key).
    aliases: [key_file]
    type: path
  client_cert:
    description:
      - The client certificate file path.
      - If not specified, it defaults to C(${HOME}/.config/lxc/client.crt).
    aliases: [cert_file]
    type: path
  trust_password:
    description:
      - The client trusted password.
      - 'You need to set this password on the LXD server before
        running this module using the following command:
        C(lxc config set core.trust_password <some random password>).
        See U(https://www.stgraber.org/2016/04/18/lxd-api-direct-interaction/).'
      - If trust_password is set, this module sends a request for
        authentication before sending any requests.
    type: str
notes:
  - Storage pools must have unique names within their scope.
  - Storage pools can use various backend drivers (dir, zfs, btrfs, lvm, ceph).
"""

EXAMPLES = """
# Create a directory-based storage pool
- name: Create a dir storage pool
  community.general.lxd_storage_pool:
    name: my-dir-pool
    driver: dir
    config:
      source: /var/lib/lxd/storage-pools/my-dir-pool
    description: "Directory-based storage pool"
    state: present

# Create a ZFS storage pool
- name: Create a ZFS storage pool
  community.general.lxd_storage_pool:
    name: my-zfs-pool
    driver: zfs
    config:
      size: 50GiB
    description: "ZFS storage pool"
    state: present

# Update pool description
- name: Update pool
  community.general.lxd_storage_pool:
    name: my-pool
    description: "Updated description"
    state: present

# Delete a storage pool
- name: Delete pool
  community.general.lxd_storage_pool:
    name: my-pool
    state: absent

# Create storage pool in a specific project
- name: Create storage pool in project
  community.general.lxd_storage_pool:
    name: project-pool
    driver: dir
    project: myproject
    state: present

# Create storage pool on a specific cluster node
- name: Create storage pool on cluster node
  community.general.lxd_storage_pool:
    name: cluster-pool
    driver: zfs
    target: node01
    config:
      source: /dev/sdb
    state: present
"""

RETURN = """
old_state:
  description: The old state of the storage pool.
  returned: success
  type: str
  sample: "absent"
logs:
  description: The logs of requests and responses.
  returned: when ansible-playbook is invoked with -vvvv.
  type: list
  sample: "(too long to be placed here)"
actions:
  description: List of actions performed for the storage pool.
  returned: success
  type: list
  sample: ["create"]
"""

import os
from typing import Any
from urllib.parse import quote, urlencode

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.general.plugins.module_utils.lxd import (
    LXDClient,
    LXDClientException,
    default_cert_file,
    default_key_file,
)

# ANSIBLE_LXD_DEFAULT_URL is a default value of the lxd endpoint
ANSIBLE_LXD_DEFAULT_URL = "unix:/var/lib/lxd/unix.socket"
ANSIBLE_LXD_DEFAULT_SNAP_URL = "unix:/var/snap/lxd/common/lxd/unix.socket"

# API endpoints
LXD_API_VERSION = "1.0"
LXD_API_STORAGE_POOLS_ENDPOINT = f"/{LXD_API_VERSION}/storage-pools"

# STORAGE_STATES is a list for states supported
STORAGE_STATES = ["present", "absent"]

# CONFIG_PARAMS is a list of config attribute names.
CONFIG_PARAMS = ["config", "description", "driver"]


class LXDStoragePoolManagement:
    def __init__(self, module: AnsibleModule) -> None:
        """Management of LXD storage pools via Ansible.

        :param module: Processed Ansible Module.
        :type module: AnsibleModule
        """
        self.module = module
        self.name = self.module.params["name"]
        self.project = self.module.params["project"]
        self._build_config()

        self.state = self.module.params["state"]
        self.target = self.module.params.get("target", None)

        self.key_file = self.module.params.get("client_key")
        if self.key_file is None:
            self.key_file = default_key_file()
        self.cert_file = self.module.params.get("client_cert")
        if self.cert_file is None:
            self.cert_file = default_cert_file()
        self.debug = self.module._verbosity >= 4

        snap_socket_path = self.module.params["snap_url"]
        if snap_socket_path.startswith("unix:"):
            snap_socket_path = snap_socket_path[5:]

        if self.module.params["url"] != ANSIBLE_LXD_DEFAULT_URL:
            self.url = self.module.params["url"]
        elif os.path.exists(snap_socket_path):
            self.url = self.module.params["snap_url"]
        else:
            self.url = self.module.params["url"]

        try:
            self.client = LXDClient(
                self.url,
                key_file=self.key_file,
                cert_file=self.cert_file,
                debug=self.debug,
            )
        except LXDClientException as e:
            self._fail_from_lxd_exception(e)

        self.trust_password = self.module.params.get("trust_password", None)
        self.actions: list[str] = []
        self.diff: dict[str, dict[str, Any]] = {"before": {}, "after": {}}
        self.old_pool_json: dict[str, Any] = {}

    def _fail_from_lxd_exception(self, exception: LXDClientException) -> None:
        """Build failure parameters from LXDClientException and fail.

        :param exception: The LXDClientException instance
        :type exception: LXDClientException
        """
        fail_params = {
            "msg": exception.msg,
            "changed": len(self.actions) > 0,
            "actions": self.actions,
            "diff": self.diff,
        }
        if self.client.debug and "logs" in exception.kwargs:
            fail_params["logs"] = exception.kwargs["logs"]
        msg = fail_params.pop("msg")
        self.module.fail_json(msg=msg, **fail_params)

    def _build_config(self) -> None:
        self.config = {}
        for attr in CONFIG_PARAMS:
            param_val = self.module.params.get(attr, None)
            if param_val is not None:
                self.config[attr] = param_val

    def _get_storage_pool_json(self) -> dict:
        url = f"{LXD_API_STORAGE_POOLS_ENDPOINT}/{quote(self.name, safe='')}"
        if self.project:
            url = f"{url}?{urlencode(dict(project=self.project))}"
        return self.client.do("GET", url, ok_error_codes=[404])

    @staticmethod
    def _pool_json_to_module_state(resp_json: dict) -> str:
        if resp_json["type"] == "error":
            return "absent"
        return "present"

    def _create_storage_pool(self) -> None:
        url = LXD_API_STORAGE_POOLS_ENDPOINT
        url_params = dict()
        if self.target:
            url_params["target"] = self.target
        if self.project:
            url_params["project"] = self.project
        if url_params:
            url = f"{url}?{urlencode(url_params)}"

        config = self.config.copy()
        config["name"] = self.name

        # Driver is required for pool creation
        if "driver" not in config:
            self.module.fail_json(msg="driver is required when creating a storage pool")

        if not self.module.check_mode:
            self.client.do("POST", url, config)
        self.actions.append("create")

    def _delete_storage_pool(self) -> None:
        url = f"{LXD_API_STORAGE_POOLS_ENDPOINT}/{quote(self.name, safe='')}"
        if self.project:
            url = f"{url}?{urlencode(dict(project=self.project))}"
        if not self.module.check_mode:
            self.client.do("DELETE", url)
        self.actions.append("delete")

    def _needs_to_change_config(self, key: str) -> bool:
        if key not in self.config:
            return False

        old_configs = self.old_pool_json.get("metadata", {}).get(key, None)

        if key == "config":
            old_config = dict(old_configs or {})
            for k, v in self.config["config"].items():
                if k not in old_config:
                    return True
                if old_config[k] != v:
                    return True
            return False
        else:
            return self.config[key] != old_configs

    def _needs_to_apply_configs(self) -> bool:
        for param in CONFIG_PARAMS:
            if param == "driver":
                # Driver cannot be changed after creation
                continue
            if self._needs_to_change_config(param):
                return True
        return False

    def _apply_storage_pool_configs(self) -> None:
        old_metadata = self.old_pool_json.get("metadata", {})
        body_json = {}

        for param in CONFIG_PARAMS:
            if param == "driver":
                # Driver cannot be changed
                if param in old_metadata:
                    body_json[param] = old_metadata[param]
                continue

            if param in old_metadata:
                body_json[param] = old_metadata[param]

            if self._needs_to_change_config(param):
                if param == "config":
                    body_json["config"] = body_json.get("config", {})
                    for k, v in self.config["config"].items():
                        body_json["config"][k] = v
                else:
                    body_json[param] = self.config[param]

        self.diff["after"] = body_json
        url = f"{LXD_API_STORAGE_POOLS_ENDPOINT}/{quote(self.name, safe='')}"
        if self.project:
            url = f"{url}?{urlencode(dict(project=self.project))}"
        if not self.module.check_mode:
            self.client.do("PUT", url, body_json=body_json)
        self.actions.append("apply_configs")

    def _manage_state(self) -> None:
        if self.state == "present":
            if self.old_state == "absent":
                self._create_storage_pool()
            else:
                if self._needs_to_apply_configs():
                    self._apply_storage_pool_configs()
        elif self.state == "absent":
            if self.old_state == "present":
                self._delete_storage_pool()

    def run(self) -> None:
        """Run the main method."""

        try:
            if self.trust_password is not None:
                self.client.authenticate(self.trust_password)

            # Get current state of the pool
            self.old_pool_json = self._get_storage_pool_json()
            self.old_state = self._pool_json_to_module_state(self.old_pool_json)

            # Set up diff
            if self.old_state == "present":
                self.diff["before"] = self.old_pool_json.get("metadata", {})
            else:
                self.diff["before"] = {}

            self.diff["after"] = self.config

            # Manage the pool state
            self._manage_state()

            state_changed = len(self.actions) > 0
            result_json = {
                "changed": state_changed,
                "old_state": self.old_state,
                "actions": self.actions,
                "diff": self.diff,
            }
            if self.client.debug:
                result_json["logs"] = self.client.logs
            self.module.exit_json(**result_json)
        except LXDClientException as e:
            self._fail_from_lxd_exception(e)


def main() -> None:
    """Ansible Main module."""

    module = AnsibleModule(
        argument_spec=dict(
            name=dict(
                type="str",
                required=True,
            ),
            project=dict(
                type="str",
            ),
            driver=dict(
                type="str",
            ),
            config=dict(
                type="dict",
            ),
            description=dict(
                type="str",
            ),
            state=dict(
                choices=STORAGE_STATES,
                default="present",
            ),
            target=dict(
                type="str",
            ),
            url=dict(
                type="str",
                default=ANSIBLE_LXD_DEFAULT_URL,
            ),
            snap_url=dict(
                type="str",
                default=ANSIBLE_LXD_DEFAULT_SNAP_URL,
            ),
            client_key=dict(
                type="path",
                aliases=["key_file"],
            ),
            client_cert=dict(
                type="path",
                aliases=["cert_file"],
            ),
            trust_password=dict(type="str", no_log=True),
        ),
        supports_check_mode=True,
    )

    lxd_manage = LXDStoragePoolManagement(module=module)
    lxd_manage.run()


if __name__ == "__main__":
    main()
