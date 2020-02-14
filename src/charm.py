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
import os
import subprocess
import charms.requirementstxt


import paramiko
from charms.osm.sshproxy import SSHProxy


class SimpleCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)

        # Load all of the events we want to observe
        for event in (
            # Charm events
            self.on.config_changed,
            self.on.install,
            self.on.upgrade_charm,

            # Charm actions
            self.on.touch_function,

            # OSM actions
            self.on.start_function,
            self.on.stop_function,
            self.on.restart_function,
            self.on.reboot_function,
            self.on.upgrade_function,

            # SSH Proxy actions
            self.on.generate_ssh_key_function,
            self.on.get_ssh_public_key_function,
            self.on.run_function,
            self.on.verify_ssh_credentials_function,
        ):
            self.framework.observe(event, self)

    def get_ssh_proxy(self):
        # TODO: Validate if the config is set
        proxy = SSHProxy(
            hostname=self.model.config["ssh-hostname"],
            username=self.model.config["ssh-username"],
            password=self.model.config["ssh-password"],
        )
        return proxy

    def on_config_changed(self, event):
        print("on_config_changed called.")

        # How do we know which key(s) changed? - We don't, at least right now.
        # Cory says Juju may one day pass that info.
        for key in self.model.config:
            print("{}={}".format(key, self.model.config[key]))

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
        proxy = self.get_ssh_proxy()

        verified = proxy.verify_credentials()
        if verified:
            unit.status = ActiveStatus()
        else:
            unit.status = BlockedStatus("Invalid SSH credentials.")

    def on_touch_function(self, event):
        filename = event.params["filename"]

        if len(self.model.config["ssh-hostname"]):
            proxy = self.get_ssh_proxy()

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

    ###############
    # OSM methods #
    ###############

    def on_start_function(self, event):
        """Start the VNF service on the VM."""
        pass

    def on_stop_function(self, event):
        """Stop the VNF service on the VM."""
        pass

    def on_restart_function(self, event):
        """Restart the VNF service on the VM."""
        pass

    def on_reboot_function(self, event):
        """Reboot the VM."""
        proxy = self.get_ssh_proxy()
        stdout, stderr = proxy.run("sudo reboot")

        if len(stderr):
            event.fail(stderr)

    def on_upgrade_function(self, event):
        """Upgrade the VNF service on the VM."""
        pass

    #####################
    # SSH Proxy methods #
    #####################
    def on_generate_ssh_key_function(self, event):
        """Generate a new SSH keypair for this unit."""

        if not SSHProxy.generate_ssh_key():
            event.fail("Unable to generate ssh key")

    def on_get_ssh_public_key_function(self, event):
        """Get the SSH public key for this unit."""

        pubkey = SSHProxy.get_ssh_public_key()

        event.set_results({"pubkey": SSHProxy.get_ssh_public_key()})

    def on_run_function(self, event):
        """Run an arbitrary command on the remote host."""

        cmd = event.params["command"]

        proxy = self.get_ssh_proxy()
        stdout, stderr = proxy.run(cmd)

        event.set_results({"output": stdout})

        if len(stderr):
            event.fail(stderr)

    def on_verify_ssh_credentials_function(self, event):
        """Verify the SSH credentials for this unit."""

        proxy = self.get_ssh_proxy()

        verified = proxy.verify_credentials()
        if verified:
            print("Verified!")
            event.set_results({"verified": True})
        else:
            print("Verification failed!")
            event.set_results({"verified": False})


if __name__ == "__main__":
    main(SimpleCharm)
