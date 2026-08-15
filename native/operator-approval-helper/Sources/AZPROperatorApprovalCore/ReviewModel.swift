import Foundation

public struct TicketReviewModel: Equatable, Sendable {
  public let approvalID: String
  public let ticketID: String
  public let lifecycle: String
  public let stage: String
  public let ticketSHA256: String
  public let issuedOn: String
  public let requestedAt: String
  public let expiresAt: String
  public let preflightResult: String
  public let actionLines: [String]
  public let prohibitedChanges: [String]
  public let rollbackRequired: Bool
  public let evidenceLines: [String]

  public init(request: DecisionRequest) throws {
    guard let ticket = request.ticket.objectValue else {
      throw ApprovalProtocolError.invalidField("ticket")
    }
    approvalID = try Self.requiredString(ticket, "approval_id")
    ticketID = try Self.requiredString(ticket, "ticket_id")
    lifecycle = try Self.requiredString(ticket, "lifecycle")
    stage = try Self.requiredString(ticket, "stage_id")
    issuedOn = try Self.requiredString(ticket, "issued_on")
    ticketSHA256 = request.ticketSHA256
    requestedAt = request.requestedAt
    expiresAt = request.expiresAt
    preflightResult = request.preflightResult

    guard let actions = ticket["actions"]?.arrayValue, !actions.isEmpty else {
      throw ApprovalProtocolError.invalidField("actions")
    }
    actionLines = try actions.map { actionValue in
      guard let action = actionValue.objectValue,
        let target = action["target"],
        let test = action["test"]?.objectValue
      else {
        throw ApprovalProtocolError.invalidField("action")
      }
      return [
        "Action: \(try Self.requiredString(action, "action_id")) — \(try Self.requiredString(action, "kind"))",
        "Target: \(CanonicalJSON.canonicalString(target))",
        "Permission: \(try Self.requiredString(action, "permission"))",
        "Expected effect: \(try Self.requiredString(action, "expected_effect"))",
        "Test: \(try Self.requiredString(test, "method"))",
        "Expected result: \(try Self.requiredString(test, "expected_result"))",
        "Stop condition: \(try Self.requiredString(action, "stop_condition"))",
      ].joined(separator: "\n")
    }

    guard let boundary = ticket["security_boundary"]?.objectValue,
      let prohibited = boundary["prohibited_changes"]?.arrayValue,
      let rollback = boundary["rollback_required"]?.boolValue
    else {
      throw ApprovalProtocolError.invalidField("security_boundary")
    }
    prohibitedChanges = try prohibited.map {
      guard let value = $0.stringValue else {
        throw ApprovalProtocolError.invalidField("prohibited_changes")
      }
      return value
    }
    rollbackRequired = rollback

    guard let evidence = ticket["evidence"]?.arrayValue, !evidence.isEmpty else {
      throw ApprovalProtocolError.invalidField("evidence")
    }
    evidenceLines = try evidence.map { itemValue in
      guard let item = itemValue.objectValue else {
        throw ApprovalProtocolError.invalidField("evidence")
      }
      return
        "\(try Self.requiredString(item, "path")) — SHA-256 \(try Self.requiredString(item, "sha256")) — \(try Self.requiredString(item, "purpose"))"
    }
  }

  public var plainText: String {
    let prohibited = prohibitedChanges.map { "• \($0)" }.joined(separator: "\n")
    let evidence = evidenceLines.map { "• \($0)" }.joined(separator: "\n")
    return """
      AZ Permit Radar Operator Decision

      Approval ID: \(approvalID)
      Ticket ID: \(ticketID)
      Lifecycle / stage: \(lifecycle) / \(stage)
      Complete ticket SHA-256: \(ticketSHA256)
      Issued: \(issuedOn)
      Requested: \(requestedAt)
      Expires: \(expiresAt)
      Preflight: \(preflightResult)

      Actions
      \(actionLines.joined(separator: "\n\n"))

      Prohibited changes
      \(prohibited)

      Rollback required: \(rollbackRequired ? "YES" : "NO")

      Evidence
      \(evidence)

      Approval permits one bounded execution attempt. It is not evidence that execution succeeded.
      """
  }

  private static func requiredString(_ object: [String: JSONValue], _ key: String) throws -> String
  {
    guard let value = object[key]?.stringValue, !value.isEmpty else {
      throw ApprovalProtocolError.invalidField(key)
    }
    return value
  }
}
