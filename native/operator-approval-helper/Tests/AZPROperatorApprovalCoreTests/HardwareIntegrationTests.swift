import Testing

@Suite(
  "Approved macOS hardware qualification",
  .disabled(
    "Requires a separately approved installation/enrollment ceremony, eligible Touch ID hardware, and a disposable governed key"
  )
)
struct HardwareIntegrationTests {
  @Test func secureEnclaveKeyIsCreatedOnlyDuringEnrollment() {}
  @Test func privateKeyExportIsImpossible() {}
  @Test func touchIDIsRequiredForSigning() {}
  @Test func passwordAndAppleWatchFallbackDoNotAuthorizeSigning() {}
  @Test func everyDecisionUsesAFreshAuthenticationContext() {}
  @Test func successfulTouchIDProducesAVerifiableSignature() {}
  @Test func cancellationLockoutAndUnavailableTouchIDFailClosed() {}
  @Test func changedFingerprintEnrollmentInvalidatesTheProtectedKey() {}
  @Test func approvedHelperSignatureAndHashChecksPass() {}
  @Test func alteredHelperBytesAreRejected() {}
}
