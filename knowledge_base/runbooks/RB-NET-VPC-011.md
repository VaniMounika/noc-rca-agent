# Runbook RB-NET-VPC-011 — Network Incidents

**Category:** Network
**Owning team:** Network Operations Team
**Primary on-call:** Farid Osman
**Escalation:** Head of Infrastructure
**Severity guidance:** P2 by default; escalate to P1 if packet loss or routing failure affects production payment or core banking traffic.

## Common symptoms
- BGP route flaps causing intermittent packet loss on transit links
- Load balancer (load-balancer-sg) marking healthy app nodes as down
- Firewall (firewall-sg-01) blocking expected ports after a configuration change
- VPC (vpc-sg-prod) peering routes not updated after subnet changes — new nodes unreachable

## Diagnosis steps
1. Check BGP session status and route flap history on transit links.
2. Check load balancer health check configuration — verify the health check endpoint path is correct for the current app version.
3. Check recent firewall rule changes against the maintenance change log.
4. Check VPC route tables for missing CIDR entries after any subnet expansion.

## Remediation steps
1. If BGP flap: typically self-resolves within ~90 seconds; add BGP flap dampening configuration to reduce recurrence.
2. If load balancer health check misconfigured: correct the health check endpoint path, redeploy config, verify traffic redistributes to healthy nodes.
3. If firewall rule blocking traffic: revert the offending rule (e.g., re-open port 5432 for app-to-DB), add a mandatory firewall change review step.
4. If VPC route table missing entries: add correct CIDR routes for new subnets, verify connectivity from new app nodes to DB tier.

## Escalation criteria
- Escalate to Head of Infrastructure if packet loss exceeds 1% for more than 5 minutes on production links.
- Notify all downstream service owners (Payment Gateway, DB Connectivity teams) if network issue is the root cause of a multi-service incident.

## Related incident categories
Often the root cause behind: DB Connectivity, Payment Gateway, FX Feed incidents (network is frequently the upstream cause).
