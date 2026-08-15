import Foundation
import LocalAuthentication
import Security

public enum SecureEnclaveSignerError: Error, Equatable {
  case keyAlreadyExists
  case keyMissing
  case accessControl
  case unsupportedAlgorithm
  case security(OSStatus)
  case signing
  case publicKey
}

public enum AZPRSecureEnclaveKeyStore {
  public static let applicationTag = "com.azpermitradar.operator-approval.secure-enclave.p256.v1"
  public static let algorithm = SecKeyAlgorithm.ecdsaSignatureMessageX962SHA256

  public static func requireEmptyEnrollmentSlot(existingKey: Bool) throws {
    if existingKey { throw SecureEnclaveSignerError.keyAlreadyExists }
  }

  public static func createForApprovedEnrollment() throws -> Data {
    try requireEmptyEnrollmentSlot(existingKey: keyExists())
    var accessError: Unmanaged<CFError>?
    guard
      let access = SecAccessControlCreateWithFlags(
        nil,
        kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        [.privateKeyUsage, .biometryCurrentSet],
        &accessError
      )
    else {
      throw SecureEnclaveSignerError.accessControl
    }
    let attributes: [CFString: Any] = [
      kSecAttrKeyType: kSecAttrKeyTypeECSECPrimeRandom,
      kSecAttrKeySizeInBits: 256,
      kSecAttrTokenID: kSecAttrTokenIDSecureEnclave,
      kSecPrivateKeyAttrs: [
        kSecAttrIsPermanent: true,
        kSecAttrApplicationTag: Data(applicationTag.utf8),
        kSecAttrAccessControl: access,
      ],
    ]
    var error: Unmanaged<CFError>?
    guard let privateKey = SecKeyCreateRandomKey(attributes as CFDictionary, &error),
      let publicKey = SecKeyCopyPublicKey(privateKey)
    else {
      throw SecureEnclaveSignerError.signing
    }
    var exportError: Unmanaged<CFError>?
    guard let bytes = SecKeyCopyExternalRepresentation(publicKey, &exportError) as Data? else {
      throw SecureEnclaveSignerError.publicKey
    }
    return bytes
  }

  public static func keyExists() throws -> Bool {
    let query: [CFString: Any] = [
      kSecClass: kSecClassKey,
      kSecAttrKeyType: kSecAttrKeyTypeECSECPrimeRandom,
      kSecAttrTokenID: kSecAttrTokenIDSecureEnclave,
      kSecAttrApplicationTag: Data(applicationTag.utf8),
      kSecReturnRef: false,
      kSecMatchLimit: kSecMatchLimitOne,
    ]
    let status = SecItemCopyMatching(query as CFDictionary, nil)
    if status == errSecSuccess { return true }
    if status == errSecItemNotFound { return false }
    throw SecureEnclaveSignerError.security(status)
  }
}

public struct SecureEnclaveDecisionSigner: DecisionSigner {
  public init() {}

  public func sign(message: Data, reason: String) throws -> SignedMaterial {
    let context = LAContext()
    context.localizedReason = String(reason.prefix(180))
    context.localizedFallbackTitle = ""
    context.touchIDAuthenticationAllowableReuseDuration = 0
    let query: [CFString: Any] = [
      kSecClass: kSecClassKey,
      kSecAttrKeyType: kSecAttrKeyTypeECSECPrimeRandom,
      kSecAttrTokenID: kSecAttrTokenIDSecureEnclave,
      kSecAttrApplicationTag: Data(AZPRSecureEnclaveKeyStore.applicationTag.utf8),
      kSecReturnRef: true,
      kSecMatchLimit: kSecMatchLimitOne,
      kSecUseAuthenticationContext: context,
    ]
    var item: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &item)
    guard status == errSecSuccess, let item else {
      if status == errSecItemNotFound { throw SecureEnclaveSignerError.keyMissing }
      throw SecureEnclaveSignerError.security(status)
    }
    let privateKey = item as! SecKey
    guard SecKeyIsAlgorithmSupported(privateKey, .sign, AZPRSecureEnclaveKeyStore.algorithm) else {
      throw SecureEnclaveSignerError.unsupportedAlgorithm
    }
    var signatureError: Unmanaged<CFError>?
    guard
      let signature = SecKeyCreateSignature(
        privateKey,
        AZPRSecureEnclaveKeyStore.algorithm,
        message as CFData,
        &signatureError
      ) as Data?
    else {
      throw SecureEnclaveSignerError.signing
    }
    guard let publicKey = SecKeyCopyPublicKey(privateKey),
      SecKeyIsAlgorithmSupported(publicKey, .verify, AZPRSecureEnclaveKeyStore.algorithm)
    else {
      throw SecureEnclaveSignerError.unsupportedAlgorithm
    }
    var exportError: Unmanaged<CFError>?
    guard let publicBytes = SecKeyCopyExternalRepresentation(publicKey, &exportError) as Data?
    else {
      throw SecureEnclaveSignerError.publicKey
    }
    return SignedMaterial(signature: signature, publicKey: publicBytes)
  }
}
