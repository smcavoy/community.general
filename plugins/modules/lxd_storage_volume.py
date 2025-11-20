#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2024, Sean McAvoy <smcavoy@users.noreply.github.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = '''
---
module: lxd_storage_volume
short_description: Manage LXD storage volumes
version_added: 9.2.0
description:
  - Management of LXD storage volumes.
  - Supports both filesystem and block content types.
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
          - Name of the storage volume.
        type: str
        required: true
    pool:
        description:
          - Name of the storage pool.
          - Required when managing volumes.
        type: str
        required: true
    project:
        description:
          - 'Project of the storage volume.
            See U(https://documentation.ubuntu.com/lxd/en/latest/projects/).'
        required: false
        type: str
    type:
        description:
          - Type of storage volume.
          - V(custom) for custom storage volumes.
          - V(container) for container volumes (read-only).
          - V(virtual-machine) for VM volumes (read-only).
          - V(image) for image volumes (read-only).
        type: str
        choices:
          - custom
          - container
          - virtual-machine
          - image
        default: custom
    content_type:
        description:
          - Content type of the storage volume.
          - V(filesystem) for filesystem-based volumes (default).
          - V(block) for block-based volumes.
        type: str
        choices:
          - filesystem
          - block
        default: filesystem
    config:
        description:
          - 'Configuration for the storage volume.
            See U(https://documentation.ubuntu.com/lxd/en/latest/api/).'
          - This can include V(size), V(snapshots.expiry), V(block.filesystem), V(block.mount_options), etc.
        type: dict
        required: false
    description:
        description:
          - Description of the storage volume.
        type: str
        required: false
    state:
        choices:
          - present
          - absent
        description:
          - Define the state of the storage volume.
        required: false
        default: present
        type: str
    target:
        description:
          - For cluster deployments. Will attempt to create a storage volume on a target node.
          - The name should match the node name you see in C(lxc cluster list).
        type: str
        required: false
    url:
        description:
          - The unix domain socket path or the https URL for the LXD server.
        required: false
        default: unix:/var/lib/lxd/unix.socket
        type: str
    snap_url:
        description:
          - The unix domain socket path when LXD is installed by snap package manager.
        required: false
        default: unix:/var/snap/lxd/common/lxd/unix.socket
        type: str
    client_key:
        description:
          - The client certificate key file path.
          - If not specified, it defaults to C(${HOME}/.config/lxc/client.key).
        required: false
        aliases: [ key_file ]
        type: path
    client_cert:
        description:
          - The client certificate file path.
          - If not specified, it defaults to C(${HOME}/.config/lxc/client.crt).
        required: false
        aliases: [ cert_file ]
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
        required: false
        type: str
notes:
  - Custom storage volumes can be attached to containers and virtual machines.
  - Block volumes require specific filesystem configuration in the config.
'''

EXAMPLES = '''
# Create a filesystem custom storage volume
- name: Create a filesystem volume
  community.general.lxd_storage_volume:
    name: my-fs-volume
    pool: my-pool
    type: custom
    content_type: filesystem
    config:
      size: 10GiB
    description: "Filesystem storage volume"
    state: present

# Create a block custom storage volume
- name: Create a block volume
  community.general.lxd_storage_volume:
    name: my-block-volume
    pool: my-pool
    type: custom
    content_type: block
    config:
      size: 20GiB
    description: "Block storage volume"
    state: present

# Resize a volume
- name: Resize volume
  community.general.lxd_storage_volume:
    name: my-volume
    pool: my-pool
    config:
      size: 30GiB
    state: present

# Update volume description
- name: Update description
  community.general.lxd_storage_volume:
    name: my-volume
    pool: my-pool
    description: "Updated description"
    state: present

# Delete a storage volume
- name: Delete volume
  community.general.lxd_storage_volume:
    name: my-volume
    pool: my-pool
    state: absent

# Create volume in a specific project
- name: Create volume in project
  community.general.lxd_storage_volume:
    name: project-volume
    pool: my-pool
    project: myproject
    state: present

# Create volume on a specific cluster node
- name: Create volume on cluster node
  community.general.lxd_storage_volume:
    name: cluster-volume
    pool: my-pool
    target: node01
    config:
      size: 15GiB
    state: present
'''

RETURN = '''
old_state:
  description: The old state of the storage volume.
  returned: success
  type: str
  sample: "absent"
logs:
  description: The logs of requests and responses.
  returned: when ansible-playbook is invoked with -vvvv.
  type: list
  sample: "(too long to be placed here)"
actions:
  description: List of actions performed for the storage volume.
  returned: success
  type: list
  sample: ["create"]
'''

import os
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.community.general.plugins.module_utils.lxd import LXDClient, LXDClientException
from ansible.module_utils.six.moves.urllib.parse import urlencode

# ANSIBLE_LXD_DEFAULT_URL is a default value of the lxd endpoint
ANSIBLE_LXD_DEFAULT_URL = 'unix:/var/lib/lxd/unix.socket'

# STORAGE_STATES is a list for states supported
STORAGE_STATES = [
    'present', 'absent'
]

# CONFIG_PARAMS is a list of config attribute names.
CONFIG_PARAMS = [
    'config', 'description'
]


class LXDStorageVolumeManagement(object):
    def __init__(self, module):
        """Management of LXD storage volumes via Ansible.

        :param module: Processed Ansible Module.
        :type module: ``object``
        """
        self.module = module
        self.name = self.module.params['name']
        self.pool = self.module.params['pool']
        self.project = self.module.params['project']
        self.volume_type = self.module.params.get('type', 'custom')
        self.content_type = self.module.params.get('content_type', 'filesystem')
        self._build_config()

        self.state = self.module.params['state']
        self.target = self.module.params.get('target', None)

        self.key_file = self.module.params.get('client_key')
        if self.key_file is None:
            self.key_file = '{0}/.config/lxc/client.key'.format(os.environ['HOME'])
        self.cert_file = self.module.params.get('client_cert')
        if self.cert_file is None:
            self.cert_file = '{0}/.config/lxc/client.crt'.format(os.environ['HOME'])
        self.debug = self.module._verbosity >= 4

        try:
            if self.module.params['url'] != ANSIBLE_LXD_DEFAULT_URL:
                self.url = self.module.params['url']
            elif os.path.exists(self.module.params['snap_url'].replace('unix:', '')):
                self.url = self.module.params['snap_url']
            else:
                self.url = self.module.params['url']
        except Exception as e:
            self.module.fail_json(msg=str(e))

        try:
            self.client = LXDClient(
                self.url, key_file=self.key_file, cert_file=self.cert_file,
                debug=self.debug
            )
        except LXDClientException as e:
            self.module.fail_json(msg=e.msg)

        self.trust_password = self.module.params.get('trust_password', None)
        self.actions = []
        self.diff = {'before': {}, 'after': {}}
        self.old_volume_json = {}

    def _build_config(self):
        self.config = {}
        for attr in CONFIG_PARAMS:
            param_val = self.module.params.get(attr, None)
            if param_val is not None:
                self.config[attr] = param_val

    def _get_storage_volume_json(self):
        url = '/1.0/storage-pools/{0}/volumes/{1}/{2}'.format(
            self.pool, self.volume_type, self.name
        )
        if self.project:
            url = '{0}?{1}'.format(url, urlencode(dict(project=self.project)))
        return self.client.do('GET', url, ok_error_codes=[404])

    @staticmethod
    def _volume_json_to_module_state(resp_json):
        if resp_json['type'] == 'error':
            return 'absent'
        return 'present'

    def _create_storage_volume(self):
        url = '/1.0/storage-pools/{0}/volumes/{1}'.format(self.pool, self.volume_type)
        url_params = dict()
        if self.target:
            url_params['target'] = self.target
        if self.project:
            url_params['project'] = self.project
        if url_params:
            url = '{0}?{1}'.format(url, urlencode(url_params))
        
        config = {}
        if 'config' in self.config:
            config['config'] = self.config['config']
        if 'description' in self.config:
            config['description'] = self.config['description']
        config['name'] = self.name
        config['type'] = self.volume_type
        config['content_type'] = self.content_type
        
        if not self.module.check_mode:
            self.client.do('POST', url, config)
        self.actions.append('create')

    def _delete_storage_volume(self):
        url = '/1.0/storage-pools/{0}/volumes/{1}/{2}'.format(
            self.pool, self.volume_type, self.name
        )
        if self.project:
            url = '{0}?{1}'.format(url, urlencode(dict(project=self.project)))
        if not self.module.check_mode:
            self.client.do('DELETE', url)
        self.actions.append('delete')

    def _needs_to_change_config(self, key):
        if key not in self.config:
            return False
        
        old_configs = self.old_volume_json.get('metadata', {}).get(key, None)
        
        if key == 'config':
            old_config = dict(old_configs or {})
            for k, v in self.config['config'].items():
                if k not in old_config:
                    return True
                if old_config[k] != v:
                    return True
            return False
        else:
            return self.config[key] != old_configs

    def _needs_to_apply_configs(self):
        for param in CONFIG_PARAMS:
            if self._needs_to_change_config(param):
                return True
        return False

    def _apply_storage_volume_configs(self):
        old_metadata = self.old_volume_json.get('metadata', {})
        body_json = {}
        
        for param in CONFIG_PARAMS:
            if param in old_metadata:
                body_json[param] = old_metadata[param]
            
            if self._needs_to_change_config(param):
                if param == 'config':
                    body_json['config'] = body_json.get('config', {})
                    for k, v in self.config['config'].items():
                        body_json['config'][k] = v
                else:
                    body_json[param] = self.config[param]
        
        self.diff['after'] = body_json
        url = '/1.0/storage-pools/{0}/volumes/{1}/{2}'.format(
            self.pool, self.volume_type, self.name
        )
        if self.project:
            url = '{0}?{1}'.format(url, urlencode(dict(project=self.project)))
        if not self.module.check_mode:
            self.client.do('PUT', url, body_json=body_json)
        self.actions.append('apply_configs')

    def _manage_state(self):
        if self.state == 'present':
            if self.old_state == 'absent':
                self._create_storage_volume()
            else:
                if self._needs_to_apply_configs():
                    self._apply_storage_volume_configs()
        elif self.state == 'absent':
            if self.old_state == 'present':
                self._delete_storage_volume()

    def run(self):
        """Run the main method."""

        try:
            if self.trust_password is not None:
                self.client.authenticate(self.trust_password)

            # Get current state of the volume
            self.old_volume_json = self._get_storage_volume_json()
            self.old_state = self._volume_json_to_module_state(self.old_volume_json)
            
            # Set up diff
            if self.old_state == 'present':
                self.diff['before'] = self.old_volume_json.get('metadata', {})
            else:
                self.diff['before'] = {}
            
            self.diff['after'] = self.config

            # Manage the volume state
            self._manage_state()

            state_changed = len(self.actions) > 0
            result_json = {
                'changed': state_changed,
                'old_state': self.old_state,
                'actions': self.actions,
                'diff': self.diff,
            }
            if self.client.debug:
                result_json['logs'] = self.client.logs
            self.module.exit_json(**result_json)
        except LXDClientException as e:
            state_changed = len(self.actions) > 0
            fail_params = {
                'msg': e.msg,
                'changed': state_changed,
                'actions': self.actions,
                'diff': self.diff,
            }
            if self.client.debug:
                fail_params['logs'] = e.kwargs.get('logs', [])
            self.module.fail_json(**fail_params)


def main():
    """Ansible Main module."""

    module = AnsibleModule(
        argument_spec=dict(
            name=dict(
                type='str',
                required=True,
            ),
            pool=dict(
                type='str',
                required=True,
            ),
            project=dict(
                type='str',
            ),
            type=dict(
                type='str',
                choices=['custom', 'container', 'virtual-machine', 'image'],
                default='custom',
            ),
            content_type=dict(
                type='str',
                choices=['filesystem', 'block'],
                default='filesystem',
            ),
            config=dict(
                type='dict',
            ),
            description=dict(
                type='str',
            ),
            state=dict(
                choices=STORAGE_STATES,
                default='present',
            ),
            target=dict(
                type='str',
            ),
            url=dict(
                type='str',
                default=ANSIBLE_LXD_DEFAULT_URL,
            ),
            snap_url=dict(
                type='str',
                default='unix:/var/snap/lxd/common/lxd/unix.socket',
            ),
            client_key=dict(
                type='path',
                aliases=['key_file'],
            ),
            client_cert=dict(
                type='path',
                aliases=['cert_file'],
            ),
            trust_password=dict(type='str', no_log=True),
        ),
        supports_check_mode=True,
    )

    lxd_manage = LXDStorageVolumeManagement(module=module)
    lxd_manage.run()


if __name__ == '__main__':
    main()
