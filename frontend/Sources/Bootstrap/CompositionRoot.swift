import AppCore
import Domain
import Infrastructure
import Foundation

/// Composition root: the single place where concrete implementations
/// are wired to abstract protocol ports.
///
/// This is the only module that imports both AppCore and Infrastructure.
package struct CompositionRoot: Sendable {
    package let documentService: DocumentService
    package let searchService: SearchService
    package let ingestionService: IngestionService
    package let entityService: EntityService
    package let collectionService: CollectionService
    package let healthRepo: any HealthPort
    package let apiClient: APIClient
    package let markdownRenderer: MarkdownRenderer
    package let thumbnailLoader: ThumbnailLoader
    package let webSocketClient: WebSocketClient
    package let spotlightIndexer: SpotlightIndexer
    package let settings: Settings

    package init(settings: Settings = .load()) {
        self.settings = settings

        let apiClient = APIClient(baseURL: settings.backendURL)
        let docRepo = APIDocumentRepository(client: apiClient)
        let searchRepo = APISearchRepository(client: apiClient)
        let healthRepo = APIHealthRepository(client: apiClient)
        let entityRepo = APIEntityRepository(client: apiClient)
        let collectionRepo = APICollectionRepository(client: apiClient)

        self.documentService = DocumentService(docRepo: docRepo)
        self.searchService = SearchService(searchRepo: searchRepo)
        self.ingestionService = IngestionService(docRepo: docRepo)
        self.entityService = EntityService(entityRepo: entityRepo)
        self.collectionService = CollectionService(collectionRepo: collectionRepo)
        self.healthRepo = healthRepo
        self.apiClient = apiClient
        self.markdownRenderer = MarkdownRenderer()
        self.thumbnailLoader = ThumbnailLoader(baseURL: settings.backendURL)
        self.webSocketClient = WebSocketClient(baseURL: settings.backendURL)
        self.spotlightIndexer = SpotlightIndexer()
    }
}
