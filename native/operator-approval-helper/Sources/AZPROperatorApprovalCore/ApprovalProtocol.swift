import CryptoKit
import Foundation

public enum ApprovalProtocolError: Error, Equatable {
  case fieldMismatch
  case invalidConstant
  case invalidField(String)
  case ticketDigestMismatch
  case unsupportedDecision
}

public enum OperatorDecision: String, Sendable {
  case approved = "APPROVED"
  case rejected = "REJECTED"
}

public enum HelperInvocationPolicy {
  public static func accepts(arguments: [String]) -> Bool {
    arguments.count == 1
  }
}

public struct DecisionRequest: Sendable {
  public static let fields: Set<String> = [
    "format_version", "record_kind", "ticket_base64", "nonce", "requested_at", "expires_at",
    "authenticator_id", "key_id", "preflight_result",
  ]

  public let ticketData: Data
  public let ticket: JSONValue
  public let nonce: String
  public let requestedAt: String
  public let expiresAt: String
  public let authenticatorID: String
  public let keyID: String
  public let preflightResult: String

  public init(canonicalData: Data) throws {
    let value = try CanonicalJSON.parseCanonical(
      canonicalData, maximumBytes: CanonicalJSON.maximumProtocolBytes)
    guard let object = value.objectValue, Set(object.keys) == Self.fields else {
      throw ApprovalProtocolError.fieldMismatch
    }
    guard object["format_version"]?.stringValue == "1.0",
      object["record_kind"]?.stringValue == "AZPR_OPERATOR_DECISION_REQUEST"
    else {
      throw ApprovalProtocolError.invalidConstant
    }
    guard let ticketBase64 = object["ticket_base64"]?.stringValue,
      let ticketData = Data(base64Encoded: ticketBase64),
      ticketData.count <= CanonicalJSON.maximumTicketBytes
    else {
      throw ApprovalProtocolError.invalidField("ticket_base64")
    }
    self.ticketData = ticketData
    ticket = try CanonicalJSON.parseCanonical(
      ticketData, maximumBytes: CanonicalJSON.maximumTicketBytes)
    guard let ticketObject = ticket.objectValue,
      try Self.nonemptyTicketIdentity(ticketObject, "approval_id"),
      try Self.nonemptyTicketIdentity(ticketObject, "ticket_id")
    else {
      throw ApprovalProtocolError.invalidField("ticket identity")
    }
    nonce = try Self.string(object, "nonce")
    guard nonce.utf8.count == 43,
      nonce.utf8.allSatisfy({
        (0x30...0x39).contains($0) || (0x41...0x5A).contains($0)
          || (0x61...0x7A).contains($0) || $0 == 0x2D || $0 == 0x5F
      })
    else {
      throw ApprovalProtocolError.invalidField("nonce")
    }
    requestedAt = try Self.string(object, "requested_at")
    expiresAt = try Self.string(object, "expires_at")
    let requestedDate = try Self.timestamp(requestedAt, "requested_at")
    let expiresDate = try Self.timestamp(expiresAt, "expires_at")
    guard expiresDate > requestedDate,
      let validity = ticketObject["validity"]?.objectValue,
      let maximumSeconds = validity["maximum_duration_seconds"]?.integerValue,
      maximumSeconds > 0,
      expiresDate <= requestedDate.addingTimeInterval(TimeInterval(maximumSeconds))
    else {
      throw ApprovalProtocolError.invalidField("expires_at")
    }
    authenticatorID = try Self.string(object, "authenticator_id")
    keyID = try Self.string(object, "key_id")
    preflightResult = try Self.string(object, "preflight_result")
    guard preflightResult == "PASS" else {
      throw ApprovalProtocolError.invalidField("preflight_result")
    }
  }

  public var ticketSHA256: String {
    SHA256.hash(data: ticketData).map { String(format: "%02x", $0) }.joined()
  }

  private static func string(_ object: [String: JSONValue], _ key: String) throws -> String {
    guard let value = object[key]?.stringValue, !value.isEmpty, value.utf8.count <= 16_384 else {
      throw ApprovalProtocolError.invalidField(key)
    }
    return value
  }

  private static func nonemptyTicketIdentity(_ object: [String: JSONValue], _ key: String) throws
    -> Bool
  {
    guard let value = object[key]?.stringValue, !value.isEmpty, value.utf8.count <= 256 else {
      throw ApprovalProtocolError.invalidField(key)
    }
    return true
  }

  private static func timestamp(_ value: String, _ field: String) throws -> Date {
    let bytes = Array(value.utf8)
    let hasUTCOffset =
      value.hasSuffix("Z")
      || (bytes.count >= 6 && (bytes[bytes.count - 6] == 0x2B || bytes[bytes.count - 6] == 0x2D)
        && bytes[bytes.count - 3] == 0x3A)
    guard hasUTCOffset else { throw ApprovalProtocolError.invalidField(field) }
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let date = formatter.date(from: value) { return date }
    formatter.formatOptions = [.withInternetDateTime]
    guard let date = formatter.date(from: value) else {
      throw ApprovalProtocolError.invalidField(field)
    }
    return date
  }
}

public struct SignedMaterial: Sendable {
  public let signature: Data
  public let publicKey: Data

  public init(signature: Data, publicKey: Data) {
    self.signature = signature
    self.publicKey = publicKey
  }
}

public protocol DecisionSigner: Sendable {
  func sign(message: Data, reason: String) throws -> SignedMaterial
}

public enum AssertionBuilder {
  public static let helperBuildID = "AZPR_OPERATOR_APPROVAL_HELPER_V1"

  public static func payload(
    request: DecisionRequest,
    decision: OperatorDecision,
    decidedAt: String,
    authenticationEventID: String
  ) -> JSONValue {
    .object([
      "format_version": .string("1.0"),
      "record_kind": .string("AZPR_OPERATOR_DECISION_ASSERTION"),
      "purpose": .string("AZPR_OPERATOR_APPROVAL_DECISION_V1"),
      "approval_id": .string(request.ticket.objectValue?["approval_id"]?.stringValue ?? ""),
      "ticket_id": .string(request.ticket.objectValue?["ticket_id"]?.stringValue ?? ""),
      "ticket_sha256": .string(request.ticketSHA256),
      "decision": .string(decision.rawValue),
      "nonce": .string(request.nonce),
      "requested_at": .string(request.requestedAt),
      "decided_at": .string(decidedAt),
      "expires_at": .string(request.expiresAt),
      "authenticator_id": .string(request.authenticatorID),
      "authentication_event_id": .string(authenticationEventID),
      "key_id": .string(request.keyID),
    ])
  }

  public static func assertion(
    request: DecisionRequest,
    decision: OperatorDecision,
    decidedAt: String,
    authenticationEventID: String,
    signer: DecisionSigner
  ) throws -> Data {
    let payload = payload(
      request: request,
      decision: decision,
      decidedAt: decidedAt,
      authenticationEventID: authenticationEventID
    )
    guard let ticket = request.ticket.objectValue,
      ticket["approval_id"]?.stringValue?.isEmpty == false,
      ticket["ticket_id"]?.stringValue?.isEmpty == false
    else {
      throw ApprovalProtocolError.invalidField("ticket identity")
    }
    let message = CanonicalJSON.canonicalData(payload)
    let reason =
      "\(decision.rawValue == "APPROVED" ? "Approve" : "Deny") \(ticket["ticket_id"]!.stringValue!) \(request.ticketSHA256.prefix(12))"
    let material = try signer.sign(message: message, reason: reason)
    guard material.publicKey.count == 65, material.publicKey.first == 0x04 else {
      throw ApprovalProtocolError.invalidField("public key encoding")
    }
    let publicDigest = SHA256.hash(data: material.publicKey).map { String(format: "%02x", $0) }
      .joined()
    let envelope = JSONValue.object([
      "signed_payload": payload,
      "signature_algorithm": .string("ECDSA_MESSAGE_X962_SHA256"),
      "signature_base64": .string(material.signature.base64EncodedString()),
      "public_key_sha256": .string(publicDigest),
      "helper_build_id": .string(helperBuildID),
    ])
    return CanonicalJSON.canonicalData(envelope)
  }

  public static func terminal(status: String, reasonCode: String) -> Data {
    CanonicalJSON.canonicalData(
      .object([
        "format_version": .string("1.0"),
        "record_kind": .string("AZPR_OPERATOR_DECISION_TERMINAL"),
        "status": .string(status),
        "reason_code": .string(reasonCode),
        "helper_build_id": .string(helperBuildID),
      ]))
  }
}
