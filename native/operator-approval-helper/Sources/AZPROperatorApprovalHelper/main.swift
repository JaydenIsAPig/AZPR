import AZPROperatorApprovalCore
import AppKit
import Foundation

private func readBoundedStandardInput() throws -> Data {
  var result = Data()
  while true {
    let chunk = try FileHandle.standardInput.read(upToCount: 32 * 1024) ?? Data()
    if chunk.isEmpty { return result }
    result.append(chunk)
    if result.count > CanonicalJSON.maximumProtocolBytes { throw StrictJSONError.oversized }
  }
}

private func emit(_ data: Data) {
  try? FileHandle.standardOutput.write(contentsOf: data)
}

@MainActor
private final class ReviewWindowController: NSObject, NSWindowDelegate {
  private let request: DecisionRequest
  private let signer = SecureEnclaveDecisionSigner()
  private var window: NSWindow!
  private var finished = false
  private var timeoutTimer: Timer?
  private var controls: [NSButton] = []

  init(request: DecisionRequest) throws {
    self.request = request
    super.init()
    let model = try TicketReviewModel(request: request)
    let size = NSSize(width: 860, height: 720)
    window = NSWindow(
      contentRect: NSRect(origin: .zero, size: size),
      styleMask: [.titled, .closable, .resizable],
      backing: .buffered,
      defer: false
    )
    window.title = "AZ Permit Radar — Operator Decision"
    window.delegate = self
    let content = NSView(frame: NSRect(origin: .zero, size: size))
    window.contentView = content

    let scroll = NSScrollView(frame: NSRect(x: 20, y: 78, width: 820, height: 622))
    scroll.hasVerticalScroller = true
    scroll.autohidesScrollers = false
    let text = NSTextView(frame: scroll.bounds)
    text.string = model.plainText
    text.isEditable = false
    text.isSelectable = true
    text.isRichText = false
    text.importsGraphics = false
    text.isAutomaticLinkDetectionEnabled = false
    text.isAutomaticDataDetectionEnabled = false
    text.isAutomaticTextReplacementEnabled = false
    text.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .regular)
    text.textContainerInset = NSSize(width: 12, height: 12)
    scroll.documentView = text
    content.addSubview(scroll)
    window.initialFirstResponder = text
    window.defaultButtonCell = nil

    let approve = button(title: "Approve", x: 580, action: #selector(approvePressed))
    let deny = button(title: "Deny", x: 690, action: #selector(denyPressed))
    let cancel = button(title: "Cancel", x: 20, action: #selector(cancelPressed))
    controls = [approve, deny, cancel]
    for control in controls {
      content.addSubview(control)
    }
  }

  func show() {
    window.center()
    window.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)
    timeoutTimer = Timer.scheduledTimer(withTimeInterval: 180, repeats: false) { [weak self] _ in
      Task { @MainActor in self?.finishTerminal(status: "TIMED_OUT", reason: "REVIEW_TIMEOUT") }
    }
  }

  private func button(title: String, x: CGFloat, action: Selector) -> NSButton {
    let button = NSButton(frame: NSRect(x: x, y: 25, width: 100, height: 34))
    button.title = title
    button.bezelStyle = .rounded
    button.keyEquivalent = ""
    button.target = self
    button.action = action
    return button
  }

  @objc private func approvePressed() { decide(.approved) }
  @objc private func denyPressed() { decide(.rejected) }
  @objc private func cancelPressed() {
    finishTerminal(status: "CANCELED", reason: "OPERATOR_CANCELED")
  }

  private func decide(_ decision: OperatorDecision) {
    for control in controls {
      control.isEnabled = false
    }
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    do {
      let assertion = try AssertionBuilder.assertion(
        request: request,
        decision: decision,
        decidedAt: formatter.string(from: Date()),
        authenticationEventID: UUID().uuidString.lowercased(),
        signer: signer
      )
      finish(assertion)
    } catch SecureEnclaveSignerError.keyMissing {
      finishTerminal(status: "UNAVAILABLE", reason: "KEY_MISSING")
    } catch {
      finishTerminal(status: "AUTHENTICATION_FAILED", reason: "SIGNATURE_FAILED")
    }
  }

  func windowShouldClose(_: NSWindow) -> Bool {
    finishTerminal(status: "CANCELED", reason: "WINDOW_CLOSED")
    return false
  }

  private func finishTerminal(status: String, reason: String) {
    finish(AssertionBuilder.terminal(status: status, reasonCode: reason))
  }

  private func finish(_ response: Data) {
    guard !finished else { return }
    finished = true
    timeoutTimer?.invalidate()
    emit(response)
    window.orderOut(nil)
    NSApp.terminate(nil)
  }
}

if !HelperInvocationPolicy.accepts(arguments: CommandLine.arguments) {
  emit(AssertionBuilder.terminal(status: "ERROR", reasonCode: "COMMAND_LINE_INPUT_FORBIDDEN"))
  exit(0)
}

do {
  let request = try DecisionRequest(canonicalData: readBoundedStandardInput())
  let app = NSApplication.shared
  app.setActivationPolicy(.regular)
  let controller = try ReviewWindowController(request: request)
  controller.show()
  app.run()
} catch {
  emit(AssertionBuilder.terminal(status: "ERROR", reasonCode: "INVALID_REQUEST"))
}
