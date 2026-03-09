from cortex.application.document_service import DocumentService
from cortex.infrastructure.file_storage import LocalFileStorage
from cortex.infrastructure.persistence.database import create_session_factory
from cortex.infrastructure.persistence.document_repo import PGDocumentRepository
from cortex.settings import Settings


class CompositionRoot:
    """Wires concrete infrastructure to abstract domain ports.

    This is the ONLY module that imports both application/ and infrastructure/.
    Application services depend on domain ports (typing.Protocol), not concrete types.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session_factory = create_session_factory(settings.database_url)

        # Infrastructure adapters
        self.file_storage = LocalFileStorage(data_dir=settings.data_dir)
        self.doc_repo = PGDocumentRepository(self.session_factory)

        # Application services (depend on ports, not concrete types)
        self.document_service = DocumentService(
            doc_repo=self.doc_repo,
            file_storage=self.file_storage,
        )

        # TODO(Step 1.4+): parser, chunker, embedder, reranker, ner, graph
        # TODO(Step 1.7): ingestion_service
        # TODO(Step 1.8): search_service
