from cortex.application.collection_service import CollectionService
from cortex.application.document_service import DocumentService
from cortex.application.entity_service import EntityService
from cortex.application.ingestion_service import IngestionService
from cortex.application.search_service import SearchService
from cortex.infrastructure.file_storage import LocalFileStorage
from cortex.infrastructure.ml.chonkie_chunker import ChonkieChunker
from cortex.infrastructure.ml.docling_parser import DoclingParser
from cortex.infrastructure.graph.age_repository import AGEGraphRepository
from cortex.infrastructure.ml.gliner_ner import GlinerNER
from cortex.infrastructure.ml.mxbai_reranker import MxbaiReranker
from cortex.infrastructure.search.graph_search import GraphSearchAdapter
from cortex.infrastructure.ml.tei_embedder import TEIEmbedder
from cortex.infrastructure.persistence.chunk_repo import PGChunkRepository
from cortex.infrastructure.persistence.entity_repo import PGEntityRepository
from cortex.infrastructure.persistence.database import create_session_factory
from cortex.infrastructure.persistence.collection_repo import PGCollectionRepository
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
        self.chunk_repo = PGChunkRepository(self.session_factory)
        self.parser = DoclingParser()
        self.chunker = ChonkieChunker(
            embedding_model=settings.chunker_embedding_model,
            chunk_size=settings.chunk_size,
        )
        self.embedder = TEIEmbedder(
            base_url=settings.embedder_url,
            model=settings.embedding_model,
        )
        self.reranker = MxbaiReranker(base_url=settings.reranker_url)
        self.ner = GlinerNER(base_url=settings.ner_url)
        self.entity_repo = PGEntityRepository(self.session_factory)
        self.collection_repo = PGCollectionRepository(self.session_factory)
        self.graph_repo = AGEGraphRepository(self.session_factory)

        # Application services (depend on ports, not concrete types)
        self.document_service = DocumentService(
            doc_repo=self.doc_repo,
            file_storage=self.file_storage,
            entity_repo=self.entity_repo,
            graph_repo=self.graph_repo,
        )
        self.ingestion_service = IngestionService(
            parser=self.parser,
            chunker=self.chunker,
            embedder=self.embedder,
            doc_repo=self.doc_repo,
            chunk_repo=self.chunk_repo,
            file_storage=self.file_storage,
            ner=self.ner,
            entity_repo=self.entity_repo,
            graph_repo=self.graph_repo,
        )

        self.entity_service = EntityService(
            entity_repo=self.entity_repo,
            graph_repo=self.graph_repo,
        )

        self.collection_service = CollectionService(
            collection_repo=self.collection_repo,
        )

        self.graph_search = GraphSearchAdapter(
            session_factory=self.session_factory,
            graph_repo=self.graph_repo,
        )

        self.search_service = SearchService(
            embedder=self.embedder,
            chunk_repo=self.chunk_repo,
            doc_repo=self.doc_repo,
            reranker=self.reranker,
            ner=self.ner,
            graph_search=self.graph_search,
            entity_repo=self.entity_repo,
        )
