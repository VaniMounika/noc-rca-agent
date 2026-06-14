# Runbook RB-PAY-GW-017 — Payment Gateway Incidents

**Category:** Payment Gateway
**Owning team:** Payments Platform Team
**Primary on-call:** Rajan Kumar
**Escalation:** Head of Payments Engineering
**Severity guidance:** P1 if any production payment gateway (SG or HK) is returning errors for settlement requests. MAS reporting required if >500 transactions affected.

## Common symptoms
- HTTP 503 / 429 responses from payment-gateway-sg, payment-gateway-hk, or visa-adapter-sg
- Spike in failed settlement transactions
- SSL/TLS handshake errors in gateway logs
- Consumer lag on settlement confirmation queue

## Diagnosis steps
1. Check upstream card network adapter health (Visa/Mastercard adapter status page and health check endpoint).
2. Check SSL certificate expiry dates for all gateway endpoints.
3. Check message queue consumer thread pool size and current backlog depth.
4. Check for recent batch re-submissions that may have triggered rate limiting.
5. Count affected transactions to determine MAS reporting threshold (>500 txns).

## Remediation steps
1. If upstream adapter is in maintenance/down: failover traffic to backup region gateway (e.g., SG → HK).
2. If SSL certificate expired: renew via automation pipeline and restart gateway service; verify TLS handshake.
3. If consumer thread pool starved: increase pool size (typical: 20 → 60) and clear backlog.
4. If rate-limited due to batch re-submission: temporarily lift rate limit via gateway admin API, re-submit in controlled batches of 100.
5. If transactions affected > 500: trigger MAS Technology Risk Management notification (see MAS Compliance Agent).

## Escalation criteria
- Escalate to Head of Payments Engineering if unresolved after 20 minutes (P1 SLA).
- Notify Compliance team immediately if MAS threshold breached, regardless of resolution status.

## Related incident categories
Often correlates with: DB Connectivity (settlement DB), Network (cross-region failover routing).
