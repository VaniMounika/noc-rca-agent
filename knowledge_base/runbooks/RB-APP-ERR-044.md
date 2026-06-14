# Runbook RB-APP-ERR-044 — Application Error Incidents

**Category:** Application Error
**Owning team:** Application Support Team
**Primary on-call:** Tanvi Sharma
**Escalation:** Head of Digital Channels
**Severity guidance:** P2 by default; escalate to P1 if mobile-banking-api or internet-banking-sg returns 500 errors for all users.

## Common symptoms
- mobile-banking-api returning null pointer / 500 errors for specific request payloads
- internet-banking-sg sessions timing out mid-transaction
- teller-app-sg failing on calls to internal pricing service
- Cascading 500 errors across multiple endpoints traced to one root component

## Diagnosis steps
1. Identify the specific request payload or input pattern triggering the error (e.g., malformed account number format).
2. Check recent release notes — was session timeout or validation logic changed recently?
3. Check downstream dependency health (e.g., internal pricing service) and circuit breaker configuration.
4. Check exception handler coverage in the failing component — is the exception unhandled and propagating?

## Remediation steps
1. If malformed input causes null pointer: add input validation/null checks at the API layer, deploy hotfix, test with known malformed payloads.
2. If session timeout too aggressive after recent release: roll back the timeout change to the previous value, schedule proper load testing before re-deploying.
3. If downstream dependency timeout uncontrolled: configure a circuit breaker with a sensible timeout and fallback response for the dependency.
4. If unhandled exception cascades: add a global exception handler, deploy fix, verify error rate returns to baseline.

## Escalation criteria
- Escalate to Head of Digital Channels if error rate exceeds 10% of total requests for more than 10 minutes.
- Notify Identity & Access team if errors originate from authentication/session layer.

## Related incident categories
Often correlates with: Auth Service (login-dependent flows), DB Connectivity (data-dependent endpoints).
