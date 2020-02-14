#!/usr/bin/env python3

import sys

sys.path.append("lib")

from ops.charm import CharmBase
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
    WaitingStatus,
    ModelError,
)
import subprocess
import charms.requirementstxt


import paramiko
from charms.osm.sshproxy import SSHProxy


class SimpleCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)

        # Load all of the events we want to observe
        for event in (
            self.on.config_changed,
            self.on.get_ssh_public_key_function,
            self.on.install,
            self.on.touch_function,
            self.on.upgrade_charm,
            self.on.verify_ssh_credentials_function,
        ):
            self.framework.observe(event, self)

    def on_config_changed(self, event):
        print("on_config_changed called.")

        # How do we know which key(s) changed? - We don't, at least right now.
        # Cory says Juju may one day pass that info.
        for key in self.model.config:
            print("{}={}".format(key, self.model.config[key]))

    def on_get_ssh_public_key_function(self, event):
        """Get the SSH public key for this unit."""
        publickey = SSHProxy.get_ssh_public_key()

        event.set_results({"pubkey": publickey})

    def on_install(self, event):
        print("on_install called.")
        unit = self.model.unit

        unit.status = MaintenanceStatus("Installing dependencies...")
        # charms.requirements.install_requirements()
        # install("paramiko")

        if not SSHProxy.has_ssh_key():
            unit.status = MaintenanceStatus("Generating SSH keys...")

            print("Generating SSH Keys")
            SSHProxy.generate_ssh_key()

        unit.status = ActiveStatus()

    def on_start(self, event):
        unit = self.model.unit

        # Unit should go into a waiting state until verify_ssh_credentials is successful
        unit.status = WaitingStatus("Waiting for SSH credentials")
        proxy = SSHProxy(
            hostname=self.model.config["ssh-hostname"],
            username=self.model.config["ssh-username"],
            password=self.model.config["ssh-password"],
        )

        verified = proxy.verify_credentials()
        if verified:
            unit.status = ActiveStatus()
        else:
            unit.status = BlockedStatus("Invalid SSH credentials.")

    def on_touch_function(self, event):
        filename = event.params["filename"]

        if len(self.model.config["ssh-hostname"]):
            proxy = SSHProxy(
                hostname=self.model.config["ssh-hostname"],
                username=self.model.config["ssh-username"],
                password=self.model.config["ssh-password"],
            )

            stdout, stderr = proxy.run("touch {}".format(filename))
            if len(stderr):
                event.set_results({"success": False})
                event.fail(stderr)
            else:
                event.set_results({"success": True})
        else:
            event.set_results({"success": False})

    def on_upgrade_charm(self, event):
        """Upgrade the charm."""
        unit = self.model.unit

        # Mark the unit as under Maintenance.
        unit.status = MaintenanceStatus("Upgrading charm")

        self.on_install(event)

        # When maintenance is done, return to an Active state
        unit.status = ActiveStatus()

    def on_verify_ssh_credentials_function(self, event):
        proxy = SSHProxy(
            hostname=self.model.config["ssh-hostname"],
            username=self.model.config["ssh-username"],
            password=self.model.config["ssh-password"],
        )

        verified = proxy.verify_credentials()
        if verified:
            print("Verified!")
            event.set_results({"verified": True})
        else:
            print("Verification failed!")
            event.set_results({"verified": False})


if __name__ == "__main__":
    main(SimpleCharm)
