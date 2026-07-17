# Source Acquisition Failure and Recovery Runbook

- **Owner:** Source operational owner named in `SourceProfile`
- **Backup/escalation:** Engineering owner, then source-access reviewer for terms/auth/access issues
- **Applies to:** Acquisition Job creation/claim, raw source acquisition, immutable artifact archival, Import Batch finalization, duplicate suppression, and manual reprocessing
- **Last tested:** 2026-07-17 against deterministic, failure, retry, and concurrent workflow tests
- **Production status:** Partial; the workflow and local transactional adapters exist, but live Tucson/Pima access, external scheduling, durable database/outbox publishing, alert transport, and production object storage are not implemented

## Detection signals

- Structured `source_acquisition` entry with outcome `failed` or repeated `retrying`.
- Structured `source_acquisition_workflow` entries or metrics showing failed, duplicate, disabled, replayed, or concurrent outcomes.
- Source health is `failing`, expected freshness is missed, or last successful acquisition stops advancing.
- Failure category is `access_review`, `access_control`, `authentication`, `authorization`, `rate_limited`, `timeout`, `network`, `remote_unavailable`, `invalid_response`, `invalid_content`, `response_too_large`, `request_limit`, `manual_input`, `artifact_storage`, or `unexpected`.
- Artifact checksum verification fails or content/volume changes unexpectedly.
- Processing queue contains no batch for expected changed content, or contains work for a duplicate/failed/skipped batch.

## Prerequisites

- Identify Acquisition Job ID, attempt, source ID, Import Batch ID, source owner, access-review status, last success, and the safe structured log entries.
- Confirm current source profile and onboarding evidence. Never copy credentials, cookies, raw payloads, or full sensitive URLs into tickets/chat/logs.
- Preserve the failed batch, logs, and any successfully stored artifact. Do not edit or delete raw artifacts.

## Safe response procedure

1. Pause new schedule triggers for the affected source if repeated requests could worsen rate limits, access concerns, or bad ingestion. Preserve the current job/batch state and do not disable unrelated sources.
2. Classify from the recorded category:
   - `access_review`, `access_control`, `authentication`, or `authorization`: stop retries; keep the source disabled/pending and escalate to the access or credential owner. Never bypass CAPTCHA or another control.
   - `rate_limited`: honor documented source limits and `Retry-After`; lower schedule/request limits before a controlled retry.
   - `timeout`, `network`, or `remote_unavailable`: verify source status through approved public channels, then use configured bounded retries. Do not increase limits broadly without contract review.
   - `invalid_response`, `invalid_content`, or `response_too_large`: compare the safe response metadata/hash with the approved fixture/contract and open source-contract review. Invalid bytes are not archived as a valid source artifact and must not be parsed inside the connector.
   - `request_limit`: inspect pagination/window assumptions; narrow the approved request scope or defer to the next run.
   - `manual_input`: verify the selected file exists under the approved upload root, is the expected type, and is within the byte limit.
   - `artifact_storage`: stop acquisition until capacity, permissions, checksum, and retention controls are verified. Never overwrite the digest path.
   - `unexpected`: capture the safe exception chain internally, add a categorized failure/test, and keep the source paused until understood.
3. For terms changes, CAPTCHA appearance, new login/access control, or explicit blocking, stop. Do not bypass or automate around the control. Set access review to pending/restricted and escalate.
4. Correct only configuration or code supported by the approved source contract. Parser corrections create a new processing result and do not modify archived bytes.
5. Retry the same failed Acquisition Job when the intent is unchanged; the workflow creates a new attempt-specific Import Batch and preserves the failed result/batch. Create a new manual job only for a distinct operator intent.
6. If an exact duplicate legitimately needs parsing again, create a manual reprocessing job referencing the archived artifact. Do not refetch, copy, or mutate the raw bytes.
7. For a crash after blob write but before metadata finalization, retry the same job. The content-addressed store verifies/reuses the blob and atomic finalization adopts it or marks the attempt duplicate.

## Verification

- One structured success entry exists with the correct source/batch IDs, SHA-256 digest, artifact reference, attempt count, and no secrets/payload.
- Artifact bytes hash to the recorded digest and the existing digest key was not overwritten.
- Source last-attempted and last-successful timestamps advance together; health returns to `healthy`.
- The Import Batch is `acquired` only for new/changed content or explicit reprocessing; duplicate batches are terminal and not queued.
- Exactly one `ArtifactAcquired` event and one normal processing decision exist for one unique Source+digest.
- Replaying a completed job does not refetch, rewrite, re-emit, or requeue.
- Freshness and volume are plausible against the documented source contract.

## Rollback and escalation

- Configuration/code rollback: restore the last reviewed profile/connector version and run against its retained fixture before resuming.
- Artifact rollback is prohibited: raw artifacts are immutable. Quarantine downstream processing by batch/reference instead of deleting or rewriting evidence.
- If metadata finalization is rolled back after blob creation, leave the content-addressed blob intact and retry; orphan cleanup requires a separately reviewed reconciliation process.
- Escalate access/terms/authentication issues to the access reviewer; storage integrity to engineering/operations; unexpected schema/content to the source owner and parser owner.
- Keep the source disabled when safe recovery or authorization cannot be demonstrated. Record the blocker, owner, and next review date.
