# Runbook RB-DB-CONN-042 — Database Connectivity Incidents

**Category:** DB Connectivity
**Owning team:** DB Operations Team
**Primary on-call:** Priya Nair
**Escalation:** Head of DB Infrastructure
**Severity guidance:** Treat as P1 if production payment or core banking DB is unreachable.

## Common symptoms
- Application logs show "connection pool exhausted" or "timeout waiting for connection"
- Gateway/API services returning 502/503/504 errors
- DB CPU or memory utilisation above 90%
- Replication lag alerts on read replicas

## Diagnosis steps
1. Check current connection pool usage on the affected service (target: payment-db-sg-01, core-banking-db-sg, reporting-db-hk).
2. Check DB server CPU, memory, and active connection count via Azure Monitor / DB metrics dashboard.
3. Check for long-running or blocking queries (`pg_stat_activity` for Postgres).
4. Verify network path (VPC route tables, security groups) between application tier and DB tier.
5. Check replica health and failover readiness.

## Remediation steps
1. If pool exhaustion: increase connection pool size (typical safe increase: 200 → 400) and recycle idle/stale connections.
2. If long-running query is blocking: identify and terminate the offending query; add a query timeout (recommended 30s) to non-critical service accounts.
3. If network routing issue: correct VPC route table entries; verify connectivity with a test query from each affected app node.
4. If primary node degraded: trigger manual failover to replica; monitor for 15 minutes before failing back.

## Escalation criteria
- Escalate to Head of DB Infrastructure if not resolved within 30 minutes for P1.
- Escalate to Compliance if transaction processing has been impacted for more than 15 minutes during business hours.

## Related incident categories
Often cascades into: Payment Gateway, Batch Job failures (if reporting DB affected).
