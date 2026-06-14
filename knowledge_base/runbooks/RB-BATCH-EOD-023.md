# Runbook RB-BATCH-EOD-023 — Batch Job Incidents

**Category:** Batch Job
**Owning team:** Batch Processing Team
**Primary on-call:** Liu Wei
**Escalation:** Head of Operations
**Severity guidance:** P3 by default; escalate to P2 if EOD reconciliation will miss its overnight completion window (impacts next-day reporting and regulatory submissions).

## Common symptoms
- eod-reconciliation, trade-settlement-batch, or report-generation-job exceeding expected runtime
- Job failure with query timeout on large tables (e.g., trade_summary, trade table)
- Job failure due to insufficient disk space in /tmp for intermediate sort/merge files
- Job dependency (e.g., FX feed) unavailable at scheduled start time

## Diagnosis steps
1. Check job runtime against historical baseline — identify which step is slow.
2. Check for missing indexes on large tables involved in the slow step (e.g., trade_date column).
3. Check /tmp disk usage for intermediate file space.
4. Check upstream dependencies (FX feed, SWIFT confirmations) completed successfully before this job started.
5. Check scheduler configuration for daylight-saving-time (DST) related timing errors.

## Remediation steps
1. If missing index causing slow query: add index on the relevant column (e.g., trade_date on trade table), re-run the batch.
2. If /tmp exhausted: clear old intermediate files from previous runs, re-run the batch.
3. If upstream dependency failed: resolve the upstream incident first (e.g., FX Feed), then re-trigger this batch; add explicit dependency health-check before batch start.
4. If DST-related scheduling error: correct the scheduler's timezone/offset configuration, re-run affected jobs in the correct window.

## Escalation criteria
- Escalate to Head of Operations if EOD reconciliation will not complete before market open.
- Notify Compliance if regulatory reporting batches (MAS submissions) are at risk of missing their deadline.

## Related incident categories
Often correlates with: FX Feed (upstream dependency), Network (data extract performance).
