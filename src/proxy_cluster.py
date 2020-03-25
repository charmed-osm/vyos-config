import socket

from ops.framework import Object, EventBase, EventsBase, EventSource, StoredState


class ClusterInitialized(EventBase):
    def __init__(self, handle, ssh_public_key, ssh_private_key):
        super().__init__(handle)
        self.ssh_public_key = ssh_public_key
        self.ssh_private_key = ssh_private_key

    def snapshot(self):
        return {
            "ssh_public_key": self.ssh_public_key,
            "ssh_private_key": self.ssh_private_key,
        }

    def restore(self, snapshot):
        self.ssh_public_key = snapshot["ssh_public_key"]
        self.ssh_private_key = snapshot["ssh_private_key"]


class ProxyClusterEvents(EventsBase):
    cluster_initialized = EventSource(ClusterInitialized)


class ProxyCluster(Object):

    on = ProxyClusterEvents()
    state = StoredState()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self._relation_name = relation_name
        self._relation = self.framework.model.get_relation(self._relation_name)

        self.framework.observe(self.on.cluster_initialized, self)

        self.state.set_default(ssh_public_key=None)
        self.state.set_default(ssh_private_key=None)

    def on_cluster_initialized(self, event):
        if not self.framework.model.unit.is_leader():
            raise RuntimeError("The initial unit of a cluster must also be a leader.")

        self.state.ssh_public_key = event.ssh_public_key
        self.state.ssh_private_key = event.ssh_private_key
        if not self.is_joined:
            event.defer()
            return

        self._relation.data[self.model.app][
            "ssh_public_key"
        ] = self.state.ssh_public_key
        self._relation.data[self.model.app][
            "ssh_private_key"
        ] = self.state.ssh_private_key

    @property
    def is_joined(self):
        return self._relation is not None

    @property
    def ssh_public_key(self):
        if self.is_joined:
            return self._relation.data[self.model.app].get("ssh_public_key")

    @property
    def ssh_private_key(self):
        if self.is_joined:
            return self._relation.data[self.model.app].get("ssh_private_key")

    @property
    def is_cluster_initialized(self):
        return (
            True
            if self._relation.data[self.model.app].get("ssh_public_key")
            and self._relation.data[self.model.app].get("ssh_private_key")
            else False
        )
