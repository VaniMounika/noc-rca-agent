# Runbook RB-AUTH-SVC-031 — Authentication Service Incidents

**Category:** Auth Service
**Owning team:** Identity & Access Team
**Primary on-call:** Mei Lin
**Escalation:** CISO Office
**Severity guidance:** P2 by default; escalate to P1 if mobile + internet banking login both affected.

## Common symptoms
- Login failures / 503 from auth-service-sg, oauth-provider-sg, mfa-service-sg
- Redis session cache memory usage near limit (>90%)
- MFA service returning rate-limit errors
- Auth service pods OOMKilled in Kubernetes

## Diagnosis steps
1. Check Redis session cache memory utilisation and eviction rate.
2. Check OAuth provider certificate validity and rotation history.
3. Check MFA service request rate — look for anomalous spikes (e.g., automated/pentest traffic).
4. Check Kubernetes pod restart counts and OOMKilled events for auth-service-sg.

## Remediation steps
1. If Redis memory exhausted: flush expired sessions, increase memory limit (typical: 4GB → 8GB), restart auth service.
2. If certificate mismatch: update OAuth provider certificate in keystore, restart service, verify token generation.
3. If MFA rate limit hit by non-user traffic: block offending IP range at firewall, clear rate limit counter, notify security team.
4. If pod OOMKilled: increase pod memory limit (typical: 512Mi → 1Gi), roll out new pod spec, monitor under load.

## Escalation criteria
- Escalate to CISO Office if root cause involves unauthorised access attempts or certificate compromise.
- Escalate to Head of Identity & Access if login failure rate exceeds 25% for more than 15 minutes.

## Related incident categories
Often correlates with: Application Error (mobile/internet banking login flows depend on auth service).
