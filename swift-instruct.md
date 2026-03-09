Structuring Swift Applications for Maintainability
The core principle is the same as in any language: separation by reason to change. Each function should do one coherent thing, each type should encapsulate one concept, each file should own one concern, and each module should group closely related concerns.
Swift gives you stronger tools to enforce this than most languages — access control with six levels of visibility, value types, protocol-oriented design, and a module system with compiler-enforced dependency boundaries. The challenge is using them deliberately rather than letting Xcode’s defaults produce a single-module monolith.
Module structure
The most important architectural decision in Swift is where you draw module boundaries. A Swift module (a target in SPM) is both a compilation unit and a visibility boundary. internal access — the default — is scoped to the module. This means your module boundaries directly determine what code can see what.
A well-structured project uses Swift Package Manager, even for apps. SPM lets you define multiple targets in a single package, each of which compiles as its own module:

MyApp/
├── Package.swift
├── Sources/
│   ├── Domain/
│   │   ├── Document.swift
│   │   └── Ports.swift
│   ├── AppCore/
│   │   ├── IngestionService.swift
│   │   └── SearchService.swift
│   ├── Infrastructure/
│   │   ├── Neo4jRepository.swift
│   │   └── QdrantRepository.swift
│   ├── Bootstrap/
│   │   ├── CompositionRoot.swift
│   │   └── Settings.swift
│   └── Entrypoints/
│       └── CLI.swift
└── Tests/
    ├── DomainTests/
    ├── AppCoreTests/
    └── InfrastructureTests/


Each directory under Sources/ is a separate target declared in Package.swift:

// Package.swift
// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "MyApp",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "myapp", targets: ["Entrypoints"]),
    ],
    targets: [
        .target(name: "Domain"),
        .target(name: "AppCore", dependencies: ["Domain"]),
        .target(name: "Infrastructure", dependencies: ["Domain"]),
        .target(name: "Bootstrap", dependencies: ["Domain", "AppCore", "Infrastructure"]),
        .executableTarget(name: "Entrypoints", dependencies: ["Bootstrap"]),

        .testTarget(name: "DomainTests", dependencies: ["Domain"]),
        .testTarget(name: "AppCoreTests", dependencies: ["Domain", "AppCore"]),
        .testTarget(name: "InfrastructureTests", dependencies: ["Domain", "Infrastructure"]),
    ]
)


A note on packageAccess: SwiftPM targets have a packageAccess parameter that controls whether package-level declarations are visible from other targets in the same package. This defaults to true, so you don’t need to spell it out on every target. If you have a target that should behave like an external client — unable to see package declarations from other targets — you can opt out with packageAccess: false. For the architecture described here, the default is what you want.
This is where Swift’s module system earns its keep. The dependencies array in Package.swift is a compiler-enforced dependency graph. If AppCore doesn’t list Infrastructure as a dependency, it literally cannot import it. You get the dependency direction rules from the Python guide, but enforced at compile time rather than by convention.
The architectural layers map the same way: Domain defines entities, value objects, and core business concepts; AppCore contains use-case orchestration; Infrastructure implements adapters to external systems; and Entrypoints exposes CLI, API, or UI surfaces. Keep transport schemas, Codable DTOs, and API request/response types separate from core domain concepts unless they are truly the same thing.
Bootstrap is the composition root — the single place where concrete implementations are wired to abstract interfaces. It is the only target that depends on both AppCore and Infrastructure, which is what keeps those two from knowing about each other. Configuration loading also lives here: reading environment variables, config files, and CLI arguments is bootstrapping work, not domain modeling.
Dependency inversion with protocols
Swift’s protocol is the natural tool for dependency inversion. It’s more powerful than Python’s typing.Protocol because conformance is checked at compile time and protocols support associated types, default implementations, and conditional conformance.
Define your abstractions in the Domain module:

// Domain/Ports.swift
package protocol GraphRepository {
    func storeRelationships(for document: Document) throws
}

package protocol VectorRepository {
    func storeEmbedding(for document: Document) throws
}


Your service depends only on these protocols:

// AppCore/IngestionService.swift
import Domain

package struct IngestionService {
    private let graphRepo: any GraphRepository
    private let vectorRepo: any VectorRepository

    package init(graphRepo: any GraphRepository, vectorRepo: any VectorRepository) {
        self.graphRepo = graphRepo
        self.vectorRepo = vectorRepo
    }

    package func ingest(title: String, content: String, metadata: [String: String] = [:]) throws -> Document {
        let doc = Document(title: title, content: content, metadata: metadata)
        try graphRepo.storeRelationships(for: doc)
        try vectorRepo.storeEmbedding(for: doc)
        return doc
    }
}


Note that the service receives already-meaningful values rather than a raw dictionary. In a real system, transport data would be validated and translated into domain values in the entrypoint or application layer before reaching the domain model. This keeps the domain clean and avoids coupling it to any particular input format.
A few Swift-specific details to note here. The any keyword before protocol types is existential syntax — it tells the compiler you’re working with a value of any type conforming to this protocol rather than a specific concrete type. For hot paths where you want the compiler to specialize, the main alternative is generic parameters, which let the compiler monomorphize. But any is the right default for service-layer dependency injection where flexibility matters more than inlining.
The ports are marked package because they need to be visible across target boundaries within the package but are not part of the package’s external public API. More on this in the access control section below.
As with the Python guide, these ports live in Domain here, but in some designs similar abstractions belong in the application layer (AppCore) instead — particularly when they represent use-case boundaries rather than core business concepts.
The composition root

// Bootstrap/CompositionRoot.swift
import Domain
import AppCore
import Infrastructure

package struct CompositionRoot {
    package let ingestionService: IngestionService
    package let searchService: SearchService

    package init(settings: Settings) {
        let graphRepo = Neo4jRepository(uri: settings.neo4jURI)
        let vectorRepo = QdrantRepository(url: settings.vectorDBURL)

        self.ingestionService = IngestionService(
            graphRepo: graphRepo,
            vectorRepo: vectorRepo
        )
        self.searchService = SearchService(
            vectorRepo: vectorRepo
        )
    }
}


Configuration loading lives alongside the composition root:

// Bootstrap/Settings.swift
import Foundation

package struct Settings: Sendable {
    package let neo4jURI: String
    package let neo4jUser: String
    package let neo4jPassword: String
    package let vectorDBURL: String

    package static func load() -> Settings {
        // In a real project, you might use swift-argument-parser for CLI args
        // or a dedicated config library. This uses ProcessInfo directly for clarity.
        let env = ProcessInfo.processInfo.environment
        return Settings(
            neo4jURI: env["NEO4J_URI"] ?? "bolt://localhost:7687",
            neo4jUser: env["NEO4J_USER"] ?? "neo4j",
            neo4jPassword: env["NEO4J_PASSWORD"]!,
            vectorDBURL: env["VECTOR_DB_URL"] ?? "http://localhost:6333"
        )
    }
}


The entrypoint depends only on Bootstrap:

// Entrypoints/CLI.swift
import Bootstrap

@main
struct CLI {
    static func main() throws {
        let settings = Settings.load()
        let root = CompositionRoot(settings: settings)
        // use root.ingestionService, root.searchService, etc.
    }
}


Value types vs. reference types
Swift gives you a choice that most languages don’t: struct (value type) vs. class (reference type). The general guidance is to default to structs and reach for classes only when you need reference semantics, identity, or inheritance.
For domain models, structs are almost always right:

// Domain/Document.swift
import Foundation

package struct Document: Sendable, Equatable {
    package let id: UUID
    package let title: String
    package let content: String
    package let metadata: [String: String]

    package init(id: UUID = UUID(), title: String, content: String, metadata: [String: String] = [:]) {
        self.id = id
        self.title = title
        self.content = content
        self.metadata = metadata
    }
}


Structs reduce accidental shared mutable state and often compose well with Sendable, but they do not automatically make code concurrency-safe. A struct can still wrap unsafe reference state, mutable globals, or non-Sendable members. The Sendable model is about whether values can be safely shared across concurrency domains, not a blanket guarantee that value types are thread-safe.
Services can be structs too, as long as they don’t hold mutable state — they’re just containers for behavior that operate on injected dependencies. Infrastructure types (database connections, network clients) are often classes because they manage resources with identity and lifecycle. That’s a legitimate use of reference semantics.
Access control as architecture
Swift has six access levels: open, public, package, internal, fileprivate, and private. In a multi-target Swift package, they become architectural tools:
	∙	public: the package’s general external API surface. Use this for types and methods that package clients (other packages that depend on yours) need to see.
	∙	open: a special case of public that applies only to classes and class members. It additionally permits subclassing and overriding from outside the defining module. Use open only when you intentionally want external clients to extend a class hierarchy.
	∙	package: visible to all targets within the same Swift package, but hidden from external clients. This is often the right visibility for ports, services, and composition-root types that must cross target boundaries internally but aren’t meant for outside consumers.
	∙	internal (the default): implementation details visible within the module/target but hidden from everything else. Most of your code lives here.
	∙	private / fileprivate: encapsulation within a type or file.
The package access level, added in Swift 5.9, is the key insight for the architecture this guide describes. In a multi-target package, many APIs need to cross target boundaries — AppCore needs to see Domain’s protocols, Bootstrap needs to see Infrastructure’s concrete types — but none of those APIs are necessarily meant for external consumers of your package. Before package existed, you had to mark everything public even when it was only shared internally. Now package lets you distinguish between “shared across my targets” and “part of my external contract.”
A practical rule: if you find yourself marking most types in a module public, ask whether they really need to be visible to external package clients or whether package is sufficient. Use public only for types that genuinely form the package’s external API.
When to split a module
The same heuristics from the Python guide apply — reason to change, single-phrase description, testability — but Swift adds a concrete one: compilation time. Each SPM target compiles independently and in parallel. Splitting a 50-file monolith into four targets can meaningfully improve incremental build times because a change in Infrastructure doesn’t recompile Domain.
Other Swift-specific signals that a module should split:
	∙	You’re marking things public or package that shouldn’t be part of any cross-module contract, just so another part of the same target can see them. That usually means those two parts belong in separate targets with a narrower interface between them.
	∙	You want to test business logic without importing infrastructure dependencies. If your test target has to link against a database driver just to test a pure calculation, your targets are too coupled.
	∙	Access control is fighting you. If you’re using @testable import extensively to reach internal members in tests, consider whether those members should be package-visible on a separate, smaller target instead.
As with Python, line count is a smell detector, not a rule. A 600-line state machine can be perfectly cohesive. A 90-line file mixing networking, parsing, and UI updates is a problem regardless of its length.
Naming and file organization
Swift convention is one primary type per file, named after the type: IngestionService.swift contains IngestionService. This is a convention, not a rule — small related types (a struct and its error type, a protocol and its default implementation) can share a file when they’re tightly coupled and short.
The same naming pitfalls from the Python guide apply:
	∙	Avoid Utilities/ or Helpers/. These become junk drawers. Put logging helpers in an Observability module, string processing in TextProcessing, etc.
	∙	Be precise about “Models.” In Swift projects, “models” can mean domain entities, Codable DTOs, Core Data managed objects, SwiftUI view models, or ML models. Use names like Domain, Schemas, DTOs, or Persistence depending on what they actually contain.
Layer-based vs. feature-based packaging
The layered layout above works well for small-to-medium projects. As a codebase grows, feature-oriented modules often become easier to navigate:

Sources/
├── DocumentFeature/
│   ├── Document.swift
│   ├── DocumentService.swift
│   ├── DocumentRepository.swift    # protocol
│   └── DocumentSchemas.swift
├── SearchFeature/
│   ├── SearchService.swift
│   ├── RankingEngine.swift
│   └── SearchSchemas.swift
├── IngestionFeature/
│   ├── IngestionPipeline.swift
│   ├── Chunking.swift
│   └── Extraction.swift
├── Infrastructure/
│   ├── Neo4jRepository.swift
│   └── QdrantRepository.swift
└── Bootstrap/
    └── CompositionRoot.swift


Each feature module owns its domain types, service logic, and port definitions. Infrastructure provides concrete implementations, and Bootstrap wires them together. As a codebase grows, this often becomes easier to navigate than a purely horizontal layer split. You can also hybridize — feature modules internally, with a shared SharedDomain module for types that genuinely cross feature boundaries.
Concurrency and Sendable
Swift’s structured concurrency (async/await, actors, Sendable) has direct architectural implications. If your services are going to be called from async contexts — and in modern Swift, they almost certainly will be — design for it from the start:

package protocol VectorRepository: Sendable {
    func storeEmbedding(for document: Document) async throws
}


Marking protocols as Sendable means any conforming type must be safe to share across concurrency domains. Domain entities that are structs with value-type properties are Sendable automatically. Services that are structs holding only Sendable dependencies are also Sendable. This is one more reason to default to value types — they tend to compose cleanly with Swift’s concurrency model, though you still need to verify that all stored properties are themselves Sendable.
If you need mutable shared state (a cache, a connection pool), reach for an actor rather than a class with manual locking.
Pipeline composition
For data pipelines, Swift’s generics give you something Python can’t easily express — the compiler verifies that each stage’s output type matches the next stage’s input type:

// IngestionFeature/Pipeline.swift
package struct Pipeline<Input: Sendable, Output: Sendable>: Sendable {
    private let work: @Sendable (Input) async throws -> Output

    package init(_ work: @escaping @Sendable (Input) async throws -> Output) {
        self.work = work
    }

    package func then<Next: Sendable>(_ next: Pipeline<Output, Next>) -> Pipeline<Input, Next> {
        Pipeline<Input, Next> { input in
            let intermediate = try await self.work(input)
            return try await next.work(intermediate)
        }
    }

    package func run(_ input: Input) async throws -> Output {
        try await work(input)
    }
}


If your chunker produces [TextChunk] and your embedder expects [TextChunk], that contract is checked at compile time.
As with the Python guide, treat this as a simple orchestration pattern. Once you need branching, retries, partial failures, or telemetry, move to an explicit orchestration service or a proper workflow system.
Testing
Keep tests aligned with the architecture: unit-test domain and application logic in isolation, integration-test infrastructure adapters against real dependencies where practical, and use a small number of end-to-end tests for entrypoints.
Because this architecture uses package visibility for cross-target APIs, test targets in the same package can see those declarations with a plain import — no special mechanism needed. @testable import is a separate tool: it grants test code access to a module’s internal members. You would use it when you deliberately want to test implementation details that aren’t part of the package-visible surface. In most cases, if your tests only exercise the package-visible API, a regular import is sufficient and preferable.
Because your services depend on protocols, test doubles are trivial. Since the protocol methods are nonmutating, use a final class for mocks that need to record calls:

// AppCoreTests/IngestionServiceTests.swift
import Domain
import AppCore

final class MockGraphRepo: GraphRepository {
    private(set) var storedDocuments: [Document] = []

    func storeRelationships(for document: Document) throws {
        storedDocuments.append(document)
    }
}


Using a final class here avoids a subtle issue: if the protocol declares a nonmutating method (the default), a struct with a mutating implementation won’t satisfy the requirement. A final class sidesteps this entirely and is the natural choice when your mock needs to accumulate state.
No mocking framework needed. The protocol conformance is checked at compile time, so your test doubles stay in sync with the real interface automatically — if you add a method to the protocol, every test double that doesn’t implement it becomes a compile error, not a runtime surprise.

The biggest differences from the Python version come down to Swift’s stronger tooling: module boundaries are compiler-enforced via SPM target dependencies, six levels of access control give you fine-grained visibility (with package being especially useful for multi-target architectures), protocol conformance is verified statically, and generics give you typed contracts between pipeline stages. The architectural principles are the same — separate by reason to change, depend on abstractions, wire at the edge — but Swift lets you lean on the compiler to enforce them rather than relying on convention and discipline alone.​​​​​​​​​​​​​​​​