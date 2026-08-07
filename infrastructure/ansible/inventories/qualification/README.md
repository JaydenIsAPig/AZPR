# Qualification inventory

This is the only H0 inventory. It is deliberately local-to-guest: copy the
repository and separately approved input bundle into the qualification host,
then invoke Ansible from an operator-controlled session inside that host. This
avoids inventing SSH credentials and keeps the playbooks portable beyond
Multipass.

`hosts.example.yml` is non-secret and safe to copy to a local ignored inventory
when a formally identified host is available. Do not turn this inventory into
staging or production by changing a variable. Create a separately authorized
physical inventory only in a later workstream.

The example variables bind the expected candidate and prompt hashes but leave
the environment ID and human approval pending. Ansible cannot change those
human gates.

