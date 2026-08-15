import CryptoKit
import Foundation
import Testing

@testable import AZPROperatorApprovalCore

private struct SoftwareP256Signer: DecisionSigner {
  let key = P256.Signing.PrivateKey()

  func sign(message: Data, reason _: String) throws -> SignedMaterial {
    let signature = try key.signature(for: message)
    return SignedMaterial(
      signature: signature.derRepresentation,
      publicKey: key.publicKey.x963Representation
    )
  }
}

private func canonicalTicket(hostile: String = "plain text only") -> Data {
  CanonicalJSON.canonicalData(
    .object([
      "format_version": .string("1.0"),
      "record_kind": .string("AZPR_APPROVAL_TICKET"),
      "approval_id": .string("AZPR-H0-OPERATORAUTH-20260811-001"),
      "ticket_id": .string("AZPR-H0-OPERATORAUTH-20260811-001"),
      "stage_id": .string("H0-OPERATORAUTH-SOURCE"),
      "title": .string("Inert operator approval source"),
      "lifecycle": .string("H0"),
      "scope": .string("OPERATORAUTH"),
      "issued_on": .string("2026-08-11"),
      "validity": .object([
        "activation_event": .string("AUTHENTICATED_DECISION"),
        "maximum_duration_seconds": .integer(300),
        "expiry_rule": .string("FIVE_MINUTES"),
      ]),
      "actions": .array([
        .object([
          "action_id": .string("ACT-001"),
          "kind": .string("FIXTURE_WRITE"),
          "target": .object(["path": .string("fixture/target.txt")]),
          "permission": .string(hostile),
          "expected_effect": .string("Bounded fixture changes"),
          "test": .object([
            "method": .string("Read fixture"),
            "expected_result": .string("PASS"),
          ]),
          "stop_condition": .string("Stop on drift"),
        ])
      ]),
      "security_boundary": .object([
        "prohibited_changes": .array([.string("No external action")]),
        "rollback_required": .bool(true),
      ]),
      "authentication_policy": .object([
        "authenticated_decision_required": .bool(true),
        "adapter": .string("TRUSTED_CONTROLLER_ADAPTER_REQUIRED"),
        "allowed_roles": .array([.string("Head of AZPR Operations")]),
        "digest_challenge_required": .bool(true),
      ]),
      "evidence": .array([
        .object([
          "path": .string("evidence.json"),
          "sha256": .string(String(repeating: "a", count: 64)),
          "purpose": .string("Fixture evidence"),
        ])
      ]),
      "related_records": .array([]),
      "notes": .array([.string("Source only")]),
      "canonicalization": .string("AZPR_CANONICAL_JSON_V1"),
      "revision": .null,
      "manifest_binding": .object([
        "path": .string("manifest.json"),
        "sha256": .string(String(repeating: "b", count: 64)),
      ]),
    ]))
}

private func canonicalRequest(ticket: Data = canonicalTicket(), extra: [String: JSONValue] = [:])
  -> Data
{
  var value: [String: JSONValue] = [
    "format_version": .string("1.0"),
    "record_kind": .string("AZPR_OPERATOR_DECISION_REQUEST"),
    "ticket_base64": .string(ticket.base64EncodedString()),
    "nonce": .string("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
    "requested_at": .string("2026-08-11T16:00:00Z"),
    "expires_at": .string("2026-08-11T16:05:00Z"),
    "authenticator_id": .string("azpr-macos-touch-id-v1"),
    "key_id": .string("azpr-operator-key-v1"),
    "preflight_result": .string("PASS"),
  ]
  value.merge(extra) { _, new in new }
  return CanonicalJSON.canonicalData(.object(value))
}

@Test func goldenCanonicalizationMatchesPythonVector() throws {
  let url = try #require(
    Bundle.module.url(forResource: "canonical-v1", withExtension: "json", subdirectory: "Fixtures"))
  let root = try #require(
    JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
  let canonicalBase64 = try #require(root["canonical_utf8_base64"] as? String)
  let expected = try #require(Data(base64Encoded: canonicalBase64))
  let valueData = try JSONSerialization.data(
    withJSONObject: try #require(root["value"]), options: [.sortedKeys, .withoutEscapingSlashes])
  let parsed = try CanonicalJSON.parseCanonical(expected, maximumBytes: 64 * 1024)
  #expect(CanonicalJSON.canonicalData(parsed) == expected)
  #expect(
    Data(SHA256.hash(data: expected)).map { String(format: "%02x", $0) }.joined() == root["sha256"]
      as? String)
  #expect(!valueData.isEmpty)
}

@Test func strictJSONRejectsDuplicateFloatNoncanonicalAndInvalidUTF8() {
  #expect(throws: StrictJSONError.self) {
    try CanonicalJSON.parseCanonical(Data(#"{"a":1,"a":2}"#.utf8), maximumBytes: 1024)
  }
  #expect(throws: StrictJSONError.self) {
    try CanonicalJSON.parseCanonical(Data(#"{"a":1.2}"#.utf8), maximumBytes: 1024)
  }
  #expect(throws: StrictJSONError.self) {
    try CanonicalJSON.parseCanonical(Data("{ \"a\":1}".utf8), maximumBytes: 1024)
  }
  #expect(throws: StrictJSONError.self) {
    try CanonicalJSON.parseCanonical(
      Data([0x7B, 0x22, 0x61, 0x22, 0x3A, 0xFF, 0x7D]), maximumBytes: 1024)
  }
}

@Test func ticketDigestIsRecomputedFromCanonicalTicketBytes() throws {
  let request = try DecisionRequest(canonicalData: canonicalRequest())
  let expected = SHA256.hash(data: request.ticketData).map { String(format: "%02x", $0) }.joined()
  #expect(request.ticketSHA256 == expected)
}

@Test func softwareP256ApprovedAndRejectedAssertionsVerify() throws {
  let request = try DecisionRequest(canonicalData: canonicalRequest())
  let signer = SoftwareP256Signer()
  for decision in [OperatorDecision.approved, .rejected] {
    let data = try AssertionBuilder.assertion(
      request: request,
      decision: decision,
      decidedAt: "2026-08-11T16:00:01Z",
      authenticationEventID: "auth-event-001",
      signer: signer
    )
    let envelope = try #require(
      try CanonicalJSON.parseCanonical(data, maximumBytes: 64 * 1024).objectValue)
    let payload = try #require(envelope["signed_payload"])
    let signatureBase64 = try #require(envelope["signature_base64"]?.stringValue)
    let signature = try #require(Data(base64Encoded: signatureBase64))
    let publicKey = try P256.Signing.PublicKey(
      x963Representation: signer.key.publicKey.x963Representation)
    let parsedSignature = try P256.Signing.ECDSASignature(derRepresentation: signature)
    #expect(publicKey.isValidSignature(parsedSignature, for: CanonicalJSON.canonicalData(payload)))
    #expect(payload.objectValue?["decision"]?.stringValue == decision.rawValue)
  }
}

@Test func cancelProducesNoSignedAssertion() throws {
  let terminal = AssertionBuilder.terminal(status: "CANCELED", reasonCode: "OPERATOR_CANCELED")
  let object = try #require(
    try CanonicalJSON.parseCanonical(terminal, maximumBytes: 1024).objectValue)
  #expect(object["record_kind"]?.stringValue == "AZPR_OPERATOR_DECISION_TERMINAL")
  #expect(object["signature_base64"] == nil)
  #expect(object["signed_payload"] == nil)
}

@Test func decisionCannotBeInjectedIntoRequest() {
  #expect(throws: ApprovalProtocolError.self) {
    _ = try DecisionRequest(
      canonicalData: canonicalRequest(extra: ["decision": .string("APPROVED")]))
  }
  #expect(HelperInvocationPolicy.accepts(arguments: ["helper"]))
  #expect(!HelperInvocationPolicy.accepts(arguments: ["helper", "--decision", "APPROVED"]))
}

@Test func duplicateEnrollmentFailsBeforeKeyCreation() {
  #expect(throws: SecureEnclaveSignerError.keyAlreadyExists) {
    try AZPRSecureEnclaveKeyStore.requireEmptyEnrollmentSlot(existingKey: true)
  }
}

@Test func reviewModelContainsEveryImmutableFieldAndHostileTextIsPlain() throws {
  let hostile = #"<a href="file:///etc/passwd">$(touch /tmp/pwned)</a>"#
  let request = try DecisionRequest(
    canonicalData: canonicalRequest(ticket: canonicalTicket(hostile: hostile)))
  let model = try TicketReviewModel(request: request)
  let text = model.plainText
  for required in [
    model.approvalID, model.ticketID, model.lifecycle, model.stage, model.ticketSHA256,
    model.issuedOn, model.requestedAt, model.expiresAt, "Preflight: PASS", "ACT-001",
    "fixture/target.txt", hostile, "Expected effect", "Expected result", "Stop condition",
    "No external action", "Rollback required: YES", "evidence.json",
    String(repeating: "a", count: 64),
    "not evidence that execution succeeded",
  ] {
    #expect(text.contains(required))
  }
}

@Test func protocolResponsesAreCanonicalAndContainNoDiagnostics() throws {
  let response = AssertionBuilder.terminal(status: "ERROR", reasonCode: "KEY_MISSING")
  let value = try CanonicalJSON.parseCanonical(response, maximumBytes: 1024)
  #expect(CanonicalJSON.canonicalData(value) == response)
  #expect(!String(decoding: response, as: UTF8.self).contains("ticket_base64"))
  #expect(!String(decoding: response, as: UTF8.self).contains("private"))
}
