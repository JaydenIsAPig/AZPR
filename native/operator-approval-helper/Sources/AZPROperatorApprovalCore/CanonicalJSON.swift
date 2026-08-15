import CoreFoundation
import Foundation

public enum StrictJSONError: Error, Equatable {
  case invalidUTF8
  case malformed
  case duplicateKey(String)
  case floatingPointForbidden
  case integerOutOfRange
  case unsupportedType
  case noncanonical
  case oversized
}

public indirect enum JSONValue: Equatable, Sendable {
  case object([String: JSONValue])
  case array([JSONValue])
  case string(String)
  case integer(Int64)
  case bool(Bool)
  case null

  public var objectValue: [String: JSONValue]? {
    if case .object(let value) = self { return value }
    return nil
  }

  public var arrayValue: [JSONValue]? {
    if case .array(let value) = self { return value }
    return nil
  }

  public var stringValue: String? {
    if case .string(let value) = self { return value }
    return nil
  }

  public var boolValue: Bool? {
    if case .bool(let value) = self { return value }
    return nil
  }

  public var integerValue: Int64? {
    if case .integer(let value) = self { return value }
    return nil
  }
}

public enum CanonicalJSON {
  public static let maximumProtocolBytes = 384 * 1024
  public static let maximumTicketBytes = 256 * 1024

  public static func parseCanonical(_ data: Data, maximumBytes: Int) throws -> JSONValue {
    guard !data.isEmpty, data.count <= maximumBytes else { throw StrictJSONError.oversized }
    guard String(data: data, encoding: .utf8) != nil else { throw StrictJSONError.invalidUTF8 }
    var scanner = JSONSyntaxScanner(Array(data))
    try scanner.scanDocument()
    let foundation: Any
    do {
      foundation = try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
    } catch {
      throw StrictJSONError.malformed
    }
    let value = try convert(foundation)
    guard canonicalData(value) == data else { throw StrictJSONError.noncanonical }
    return value
  }

  public static func canonicalData(_ value: JSONValue) -> Data {
    Data(canonicalString(value).utf8)
  }

  public static func canonicalString(_ value: JSONValue) -> String {
    switch value {
    case .object(let object):
      let keys = object.keys.sorted { left, right in
        Array(left.utf8).lexicographicallyPrecedes(Array(right.utf8))
      }
      return "{"
        + keys.map { "\(escape($0)):\(canonicalString(object[$0]!))" }.joined(separator: ",") + "}"
    case .array(let array):
      return "[" + array.map(canonicalString).joined(separator: ",") + "]"
    case .string(let string):
      return escape(string)
    case .integer(let integer):
      return String(integer)
    case .bool(let value):
      return value ? "true" : "false"
    case .null:
      return "null"
    }
  }

  private static func escape(_ value: String) -> String {
    var result = "\""
    for scalar in value.unicodeScalars {
      switch scalar.value {
      case 0x08: result += "\\b"
      case 0x09: result += "\\t"
      case 0x0A: result += "\\n"
      case 0x0C: result += "\\f"
      case 0x0D: result += "\\r"
      case 0x22: result += "\\\""
      case 0x5C: result += "\\\\"
      case 0x00...0x1F: result += String(format: "\\u%04x", scalar.value)
      default: result.unicodeScalars.append(scalar)
      }
    }
    return result + "\""
  }

  private static func convert(_ value: Any) throws -> JSONValue {
    if value is NSNull { return .null }
    if let string = value as? String { return .string(string) }
    if let array = value as? [Any] { return .array(try array.map(convert)) }
    if let object = value as? [String: Any] {
      return .object(try object.mapValues(convert))
    }
    if let number = value as? NSNumber {
      if CFGetTypeID(number) == CFBooleanGetTypeID() { return .bool(number.boolValue) }
      let decimal = number.decimalValue
      var rounded = Decimal()
      var source = decimal
      NSDecimalRound(&rounded, &source, 0, .plain)
      guard rounded == decimal else { throw StrictJSONError.floatingPointForbidden }
      let text = NSDecimalNumber(decimal: decimal).stringValue
      guard let integer = Int64(text) else { throw StrictJSONError.integerOutOfRange }
      return .integer(integer)
    }
    throw StrictJSONError.unsupportedType
  }
}

private struct JSONSyntaxScanner {
  private let bytes: [UInt8]
  private var index = 0

  init(_ bytes: [UInt8]) {
    self.bytes = bytes
  }

  mutating func scanDocument() throws {
    try scanValue()
    guard index == bytes.count else { throw StrictJSONError.malformed }
  }

  private mutating func scanValue() throws {
    guard index < bytes.count else { throw StrictJSONError.malformed }
    switch bytes[index] {
    case 0x7B: try scanObject()
    case 0x5B: try scanArray()
    case 0x22: _ = try scanString()
    case 0x74: try scanLiteral("true")
    case 0x66: try scanLiteral("false")
    case 0x6E: try scanLiteral("null")
    case 0x2D, 0x30...0x39: try scanInteger()
    default: throw StrictJSONError.malformed
    }
  }

  private mutating func scanObject() throws {
    index += 1
    if consume(0x7D) { return }
    var keys = Set<String>()
    while true {
      let key = try scanString()
      guard keys.insert(key).inserted else { throw StrictJSONError.duplicateKey(key) }
      guard consume(0x3A) else { throw StrictJSONError.malformed }
      try scanValue()
      if consume(0x7D) { return }
      guard consume(0x2C) else { throw StrictJSONError.malformed }
    }
  }

  private mutating func scanArray() throws {
    index += 1
    if consume(0x5D) { return }
    while true {
      try scanValue()
      if consume(0x5D) { return }
      guard consume(0x2C) else { throw StrictJSONError.malformed }
    }
  }

  private mutating func scanString() throws -> String {
    guard index < bytes.count, bytes[index] == 0x22 else { throw StrictJSONError.malformed }
    let start = index
    index += 1
    while index < bytes.count {
      let byte = bytes[index]
      if byte == 0x22 {
        index += 1
        let literal = Data(bytes[start..<index])
        do { return try JSONDecoder().decode(String.self, from: literal) } catch {
          throw StrictJSONError.malformed
        }
      }
      if byte < 0x20 { throw StrictJSONError.malformed }
      if byte == 0x5C {
        index += 1
        guard index < bytes.count else { throw StrictJSONError.malformed }
        if bytes[index] == 0x75 {
          guard index + 4 < bytes.count else { throw StrictJSONError.malformed }
          for offset in 1...4 where !isHex(bytes[index + offset]) {
            throw StrictJSONError.malformed
          }
          index += 5
          continue
        }
        guard [0x22, 0x5C, 0x2F, 0x62, 0x66, 0x6E, 0x72, 0x74].contains(bytes[index]) else {
          throw StrictJSONError.malformed
        }
      }
      index += 1
    }
    throw StrictJSONError.malformed
  }

  private mutating func scanInteger() throws {
    if consume(0x2D), index == bytes.count { throw StrictJSONError.malformed }
    if consume(0x30) {
      if index < bytes.count, (0x30...0x39).contains(bytes[index]) {
        throw StrictJSONError.malformed
      }
    } else {
      guard index < bytes.count, (0x31...0x39).contains(bytes[index]) else {
        throw StrictJSONError.malformed
      }
      while index < bytes.count, (0x30...0x39).contains(bytes[index]) { index += 1 }
    }
    if index < bytes.count, [0x2E, 0x45, 0x65].contains(bytes[index]) {
      throw StrictJSONError.floatingPointForbidden
    }
  }

  private mutating func scanLiteral(_ value: String) throws {
    let expected = Array(value.utf8)
    guard index + expected.count <= bytes.count,
      Array(bytes[index..<index + expected.count]) == expected
    else {
      throw StrictJSONError.malformed
    }
    index += expected.count
  }

  private mutating func consume(_ byte: UInt8) -> Bool {
    guard index < bytes.count, bytes[index] == byte else { return false }
    index += 1
    return true
  }

  private func isHex(_ byte: UInt8) -> Bool {
    (0x30...0x39).contains(byte) || (0x41...0x46).contains(byte) || (0x61...0x66).contains(byte)
  }
}
