// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Cortex",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "Cortex", targets: ["CortexApp"]),
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-markdown", from: "0.4.0"),
    ],
    targets: [
        // Domain: entities, value objects, port protocols. No external deps.
        .target(name: "Domain"),

        // AppCore: use-case orchestration. Depends only on Domain.
        .target(name: "AppCore", dependencies: ["Domain"]),

        // Infrastructure: API client, WebSocket, markdown rendering. Depends only on Domain.
        .target(name: "Infrastructure", dependencies: [
            "Domain",
            .product(name: "Markdown", package: "swift-markdown"),
        ]),

        // Bootstrap: composition root + settings. Depends on all above.
        .target(name: "Bootstrap", dependencies: ["Domain", "AppCore", "Infrastructure"]),

        // CortexApp: SwiftUI views + @main entry point. Depends on Bootstrap.
        .executableTarget(name: "CortexApp", dependencies: ["Bootstrap"]),

        // Tests aligned with architecture
        .testTarget(name: "DomainTests", dependencies: ["Domain"]),
        .testTarget(name: "AppCoreTests", dependencies: ["Domain", "AppCore"]),
        .testTarget(name: "InfrastructureTests", dependencies: ["Domain", "Infrastructure"]),
    ]
)
