# Runbook RB-FX-FEED-008 — FX Rate Feed Incidents

**Category:** FX Feed
**Owning team:** Market Data Team
**Primary on-call:** Ahmed Hassan
**Escalation:** Head of Market Data
**Severity guidance:** P2 by default; escalate to P1 if FX desk cannot execute trades due to stale/missing rates.

## Common symptoms
- fx-rate-feed-apac, reuters-adapter-sg, or bloomberg-feed-hk reporting stale or missing rates
- Feed latency exceeding 5-second SLA
- Adapter deserialization errors in logs
- FX desk reporting incorrect or frozen rates on trading screens

## Diagnosis steps
1. Check TCP connection status between adapter and upstream feed provider (Reuters RMDS / Bloomberg).
2. Check feed latency metrics against the 5-second SLA.
3. Check adapter logs for deserialization or schema-mismatch errors (e.g., unexpected new field in FIX message).
4. Verify primary/secondary failover configuration is correctly pointing to live endpoints.

## Remediation steps
1. If TCP connection lost: manually restart the adapter and configure automatic reconnect with exponential backoff.
2. If cross-border network congestion (e.g., SG-HK link): temporarily reroute feed via alternate link (e.g., HK-Tokyo), engage network team for root fix.
3. If schema mismatch: apply updated deserialization config matching the new upstream schema, restart adapter, verify all FX pairs publish correctly.
4. If failover misconfigured: correct primary/secondary endpoint config, run a manual failover test to confirm automatic switchover works.

## Escalation criteria
- Escalate to Head of Market Data if FX desk cannot price trades for more than 10 minutes.
- Notify Batch Processing Team — downstream EOD jobs depend on FX feed availability.

## Related incident categories
Often correlates with: Batch Job (EOD reconciliation depends on FX rates), Network (cross-region links).
