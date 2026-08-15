// swift-tools-version: 6.0
import PackageDescription

let package = Package(
  name: "AZPROperatorApprovalHelper",
  platforms: [.macOS(.v13)],
  products: [
    .library(name: "AZPROperatorApprovalCore", targets: ["AZPROperatorApprovalCore"]),
    .executable(name: "azpr-operator-approval-helper", targets: ["AZPROperatorApprovalHelper"]),
  ],
  targets: [
    .target(name: "AZPROperatorApprovalCore"),
    .executableTarget(
      name: "AZPROperatorApprovalHelper",
      dependencies: ["AZPROperatorApprovalCore"]
    ),
    .testTarget(
      name: "AZPROperatorApprovalCoreTests",
      dependencies: ["AZPROperatorApprovalCore"],
      resources: [.copy("Fixtures")]
    ),
  ]
)
