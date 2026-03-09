Structuring Python Applications for Maintainability
The core principle is separation by reason to change. This applies fractally: each function should do one coherent thing, each class should encapsulate one concept, each module should own one concern, and each package should group closely related concerns.
The goal isn’t small files for their own sake — it’s that any given change should touch as few modules as possible.
Project layout
A production-grade project uses a src/ layout with pyproject.toml. PyPA recommends this because it prevents accidentally importing the in-development copy of your package instead of the installed one:

project-root/
├── pyproject.toml
├── src/
│   └── myapp/
│       ├── __init__.py
│       ├── __main__.py          # entry point for python -m myapp
│       ├── bootstrap.py         # composition root — wires dependencies
│       ├── settings.py
│       ├── domain/
│       │   ├── document.py      # entities, value objects
│       │   └── ports.py         # abstract interfaces (Protocols)
│       ├── application/
│       │   ├── ingestion_service.py
│       │   └── search_service.py
│       ├── infrastructure/
│       │   ├── neo4j_repository.py
│       │   └── vector_repository.py
│       └── entrypoints/
│           └── cli.py
└── tests/


__main__.py is the Python-native entry point for running your package as python -m myapp. Use main.py for script-oriented apps, but prefer __main__.py for distributable packages.
The directory names map to architectural layers: domain/ defines entities, value objects, and core business concepts; application/ contains use-case orchestration; infrastructure/ implements adapters to external systems; and entrypoints/ exposes CLI or API surfaces. Keep transport schemas, ORM models, and API request/response types separate from core domain concepts unless they are truly the same thing — collapsing those distinctions is one of the most common architectural mistakes in Python codebases.
bootstrap.py is the composition root — the single place where you wire concrete implementations to abstract interfaces. Keeping object wiring in a single composition root rather than scattering construction logic across modules is one of the most useful practical rules for maintaining clean dependency graphs.
Dependency direction and inversion
Architectural dependencies should point inward: entrypoints call application services, application logic depends on domain types and abstract ports, and infrastructure provides concrete implementations of those ports. The composition root sits at the edge and wires the pieces together. The critical detail is that services should depend on interfaces, not concrete implementations.
Define your abstractions in the domain or application layer using typing.Protocol, depending on whether the abstraction is part of the core business model or a use-case boundary. Protocol gives you structural subtyping without requiring inheritance:

# domain/ports.py
from typing import Protocol
from myapp.domain.document import Document

class GraphRepository(Protocol):
    def store_relationships(self, doc: Document) -> None: ...

class VectorRepository(Protocol):
    def store_embedding(self, doc: Document) -> None: ...


In this example, the repository ports live in domain/ports.py, but in some designs similar abstractions belong in the application layer instead — particularly when they represent use-case boundaries rather than core business concepts.
Your service depends only on these protocols:

# application/ingestion_service.py
from typing import Any, Mapping

from myapp.domain.document import Document
from myapp.domain.ports import GraphRepository, VectorRepository

class IngestionService:
    def __init__(self, graph_repo: GraphRepository, vector_repo: VectorRepository):
        self.graph_repo = graph_repo
        self.vector_repo = vector_repo

    def ingest_document(self, raw_data: Mapping[str, Any]) -> Document:
        doc = Document.from_raw(raw_data)
        self.graph_repo.store_relationships(doc)
        self.vector_repo.store_embedding(doc)
        return doc


The concrete Neo4j and vector DB implementations live in infrastructure/ and satisfy these protocols structurally — no base class registration needed. Your composition root (bootstrap.py) is where you wire concrete implementations to abstract interfaces. This means you can swap Neo4j for a test double or replace your vector DB without touching any service code.
A note on domain models: the design goal is that domain models should not depend on infrastructure. They may still depend on the standard library, typing, validation libraries, or small domain-local helpers. “Depend on nothing” is a useful slogan but too absolute in practice.
__init__.py and package APIs
Use __init__.py to define a package’s public surface area, but keep it lightweight and free of side effects (importing a package executes its __init__.py). Re-export commonly used names when it improves ergonomics, but avoid overusing re-exports to the point that callers can no longer tell where important types actually live:

# infrastructure/__init__.py
from .neo4j_repository import Neo4jRepository
from .vector_repository import VectorRepository

__all__ = ["Neo4jRepository", "VectorRepository"]


A precision worth knowing: from myapp.infrastructure import Neo4jRepository works because the from .neo4j_repository import Neo4jRepository line binds the name into the package namespace. __all__ specifically controls what from package import * exposes — it doesn’t make direct imports work.
Also note that __init__.py is only required for regular packages. Python also supports namespace packages (without __init__.py), though regular packages are usually the clearest choice for application code.
Configuration
Centralize configuration into a dedicated module and pass it explicitly. Pydantic’s BaseSettings validates types, reads from environment variables and dotenv files, and gives you a single typed source of truth. Use the current model_config mechanism rather than the older inner Config class:

# settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str
    vector_db_url: str = "http://localhost:6333"


When to split a module
Line count is a useful smell detector but not a rule. A 600-line parser can be perfectly cohesive. A 90-line file can be terrible if it mixes persistence, validation, business logic, and formatting. Better indicators:
	∙	Does this file have more than one reason to change? If Neo4j schema changes and embedding logic changes both require editing the same file, split it.
	∙	Can you describe the file’s purpose in one short phrase? If you need “and” in the description, it’s doing too much.
	∙	Are there internal function clusters that don’t reference each other? Groups of functions that only call each other but never interact with another group are begging to be separate modules.
	∙	Can you test it in isolation? If testing one behavior requires setting up infrastructure for an unrelated behavior in the same module, that’s a strong signal.
Cohesion, change frequency, review friction, and testability are better guides than raw line count.
Naming pitfalls
Two common directory names that cause problems at scale:
	∙	utils/ is dangerous. It becomes a junk drawer for unrelated helpers — effectively miscellaneous.py spread across files. If something is about logging, put it under observability/ or logging_config.py. Text parsing goes under text/ or parsing/. Reserve utils/ as a last resort for truly generic, dependency-light helpers, and be aggressive about graduating things out of it.
	∙	models/ is ambiguous. In Python projects, “models” can mean domain entities, ORM tables, Pydantic schemas, API request/response shapes, or ML models. In a nontrivial project, use precise names: domain/, schemas/, entities/, or db_models/ depending on what they actually contain.
Layer-based vs. feature-based packaging
The layered layout above (global application/, infrastructure/, domain/) is good for explaining separation of concerns and works well for small-to-medium projects. But feature-oriented packaging often scales better once the codebase grows:

src/myapp/
├── documents/
│   ├── service.py
│   ├── repository.py
│   ├── schemas.py
│   └── cli.py
├── search/
│   ├── service.py
│   ├── ranking.py
│   └── schemas.py
└── ingestion/
    ├── pipeline.py
    ├── chunking.py
    └── extraction.py


This keeps related code co-located. When you’re working on document ingestion, everything you need is in one directory rather than spread across four top-level folders. As a codebase grows, this often becomes easier to navigate than a purely horizontal layer split. You can also hybridize — feature packages internally, with a shared domain/ for cross-cutting abstractions.
Circular imports
Circular imports tend to fail when two modules need names from each other during top-level import, especially with from module import name style. There are a few escape hatches: moving an import inside a function body works pragmatically (the Python FAQ mentions this explicitly), and TYPE_CHECKING blocks let you import names only for type-checking without creating runtime cycles.
Architecturally though, a circular import usually signals a design problem. Prefer extracting the shared concept into a third module or inverting the dependency via a Protocol.
Pipeline composition
For data pipelines (parse → chunk → embed → store in vector DB → extract entities → store in Neo4j), a simple orchestration pattern works well as a starting point:

# ingestion/pipeline.py
from typing import Any, Callable

class Pipeline:
    def __init__(self) -> None:
        self.steps: list[Callable[[Any], Any]] = []

    def add_step(self, step: Callable[[Any], Any]) -> "Pipeline":
        self.steps.append(step)
        return self

    def run(self, data: Any) -> Any:
        for step in self.steps:
            data = step(data)
        return data


Each step can live in its own module and be tested independently. The Callable[[Any], Any] typing is intentionally simplified here — when you want typed stage-to-stage contracts, generics are the natural next step.
However, treat this as a simple orchestration pattern, not as an end-state architecture. Once you need branching, retries, partial failures, async steps, or telemetry, this abstraction gets thin. At that point you typically want either a small explicit orchestration service with named steps (when the workflow is simple and stable) or a real workflow/job system (when you need branching, retries, or external coordination).
Testing
Keep tests aligned with the architecture: unit-test domain and application logic in isolation, integration-test infrastructure adapters against real dependencies where practical, and use a small number of end-to-end tests for entrypoints. Because your services depend on Protocols rather than concrete implementations, you can substitute test doubles without any mocking framework — just pass in an object that satisfies the protocol.

For simplicity, this example uses Document.from_raw(...), but in larger systems raw transport data is often validated and translated into domain objects in the application layer rather than inside the entity itself.

validated = IngestionInput.from_mapping(raw_data)
doc = Document(
    id=validated.id,
    text=validated.text,
    metadata=validated.metadata,
)