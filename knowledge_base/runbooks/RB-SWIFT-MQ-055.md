# Runbook RB-SWIFT-MQ-055 — SWIFT Message Queue Incidents

**Category:** SWIFT Queue
**Owning team:** Messaging Infrastructure Team
**Primary on-call:** Sanjay Patel
**Escalation:** Head of Correspondent Banking
**Severity guidance:** P2 by default; escalate to P1 if outbound SWIFT messages to correspondent banks are blocked for more than 30 minutes (regulatory cutover risk).

## Common symptoms
- Growing backlog of unprocessed outbound SWIFT messages on swift-mq-sg-01
- ACK processor (swift-ack-processor) thread count dropped to zero
- /var/mqm disk partition usage above 85%
- Outbound message rejections from correspondent banks (BIC certificate errors)

## Diagnosis steps
1. Check swift-mq-sg-01 disk usage, specifically /var/mqm partition.
2. Check ACK processor thread/process status — is it deadlocked or crashed?
3. Check for split-brain condition between primary and backup MQ nodes (network partition).
4. Check SWIFT BIC certificate expiry dates.

## Remediation steps
1. If disk space exhausted: clear old message persistence logs from /var/mqm (typical recovery: free 50-100GB), restart MQ broker, process backlog.
2. If ACK processor deadlocked: restart the processor; add deadlock detection timeout (recommended 60s) to prevent recurrence.
3. If split-brain detected: force primary election on both nodes, verify message processing resumes, add split-brain detection alerting.
4. If BIC certificate expired: renew via SWIFT portal, restart outbound message processor, confirm ACKs received from correspondent banks.

## Escalation criteria
- Escalate to Head of Correspondent Banking if outbound messages blocked > 30 minutes — risk of missing same-day settlement cutover.
- Notify Compliance if any SWIFT message related to a transaction above MAS reporting threshold is delayed.

## Related incident categories
Often correlates with: Network (split-brain scenarios), Batch Job (settlement batches depend on SWIFT confirmations).
