---
document_id: backend-structure
version: 1.2
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Backend Structure v1.2

## Status statement

**Implemented:** the v1.1 domain/application kernel plus a framework-neutral source registry profile, connector/acquisition ports, acquisition coordinator, deterministic fake connector, manual fixture connector, local content-addressed artifact store, and JSON-lines/in-memory acquisition logging.

**Partially implemented:** raw acquisition works for deterministic and manually supplied files. Network protocols are defined, but no live municipal connector, HTTP client, scheduler, persistent registry, production object store, parser, or monitoring backend is selected.

## Source profile contract

`SourceProfile` describes heterogeneous sources without embedding provider response models. It records:

- jurisdiction identity and display name;
- source name and acquisition method (`file_download`, `http_api`, `html_page`, or `manual_upload`);
- non-secret endpoint URL, query, and header configuration;
- media type and file extension;
- schedule and IANA time zone;
- authentication requirement, without credentials;
- parser identifier/version and expected date/unique-identifier fields;
- historical availability and known limitations;
- enabled state, last attempted/successful acquisition, and health status;
- terms/access-review status and operational owner.

Network sources require an absolute HTTP(S) endpoint. URLs containing credentials and secret-bearing headers are rejected. Disabled profiles must report disabled health. A successful timestamp cannot exist without an attempt timestamp.

## Connector boundaries

The application layer defines a common raw `AcquisitionConnector` plus explicit `FileDownloadConnector`, `HttpApiConnector`, `HtmlPageConnector`, and `ManuallyUploadedFileConnector` protocols. A connector receives the source profile and `RequestPolicy`, then returns only `RawAcquisition` bytes, media type, source reference, acquisition timestamp, and non-secret metadata.

No connector may parse rows, create `SourceRecord` or `Permit`, bypass CAPTCHA, defeat access controls, or persist credentials. The parser boundary begins only after immutable artifact registration.

Implemented adapters are intentionally limited to:

- `FakeConnector`, which returns a deterministic sequence of raw outcomes for tests;
- `ManualFixtureConnector`, which reads one file contained by an explicitly approved fixture root.

No Tucson/Pima live adapter is implemented because governed business data contains no approved source and no sufficiently understood contract.

## Acquisition policy and flow

`RequestPolicy` requires an explicit user agent, positive timeout, per-run request limit, response-byte limit, and retry policy. The coordinator caps attempts at the lower of the retry maximum and request limit, applies deterministic exponential backoff, and retries only errors explicitly marked retryable.

```text
SourceProfileRegistry -> access/method preflight -> connector raw bytes
  -> SHA-256 digest -> immutable artifact store -> SourceArtifact metadata
  -> profile health/timestamps -> structured acquisition log
```

Terms/access status must be `approved` or `not_required`. Pending/restricted access fails before connector execution. Access-control/CAPTCHA detection, authentication, and authorization have separate stop categories; other categories include configuration, access review, rate limit, timeout, network, remote availability, invalid/oversized response, request limit, manual input, artifact storage, and unexpected failure.

## Artifact integrity and idempotency

The local store recomputes SHA-256, uses the digest as the storage key, writes and fsyncs a temporary file, sets read-only permissions, atomically links it to the create-once target, and verifies bytes whenever the key already exists. Reacquiring identical bytes returns the same storage reference and does not overwrite. `SourceArtifact` remains frozen and associates digest/storage metadata with the current Import Batch.

Local read-only permissions are not a substitute for production object lock, retention policy, backup, or access control. Those deployment controls remain not selected.

## Observability and sensitive-data handling

Each attempt emits a structured entry with source ID, batch ID, timestamp, outcome, attempt, safe failure category/message, digest/reference when successful, and elapsed milliseconds. Logs exclude raw payloads, headers, URL query values, and credentials. JSON-lines persistence is append-only at the application level; production log shipping/retention is not selected.

## Existing aggregate and repository contracts

The aggregate boundaries, lifecycles, CQRS messages, and repository ports from [backend structure v1.1](backend-structure-v1.1.md) remain in force. The acquisition coordinator does not replace the future Import Batch use-case transaction or persistent Source Artifact repository.

## Related current documents

- [Project structure v1.2](../project-structure/project-structure-v1.2.md)
- [Business logic v1.2](../business-logic/business-logic-v1.2.md)
- [Business data v1.0](../../current/business-data-v1.0.json)
- [Source onboarding checklist](../../governance/source-onboarding-checklist.md)
- [Source acquisition runbook](../../runbooks/source-acquisition.md)
- [Backend structure log](../../logs/backend-structure-log-v1.2.md)
