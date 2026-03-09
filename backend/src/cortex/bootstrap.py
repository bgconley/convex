from cortex.infrastructure.persistence.database import create_session_factory
from cortex.settings import Settings


class CompositionRoot:
    """Wires concrete infrastructure to abstract domain ports.

    This is the ONLY module that imports both application/ and infrastructure/.
    Application services depend on domain ports (typing.Protocol), not concrete types.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session_factory = create_session_factory(settings.database_url)

        # Infrastructure adapters will be created here as steps progress:
        # self.file_storage = LocalFileStorage(data_dir=settings.data_dir)
        # self.parser = DoclingParser()
        # self.chunker = ChonkieChunker(embedding_model=settings.embedding_model)
        # self.embedder = TEIEmbedder(base_url=settings.embedder_url)
        # self.reranker = MxbaiReranker()
        # self.ner = GlinerNER()
        # self.doc_repo = PGDocumentRepository(self.session_factory)
        # self.chunk_repo = PGChunkRepository(self.session_factory)
        # self.graph_repo = AGEGraphRepository(self.session_factory)

        # Application services will be wired here as steps progress:
        # self.document_service = DocumentService(doc_repo=..., file_storage=...)
        # self.ingestion_service = IngestionService(parser=..., chunker=..., ...)
        # self.search_service = SearchService(embedder=..., reranker=..., ...)
