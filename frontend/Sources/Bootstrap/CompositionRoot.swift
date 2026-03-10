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
    package let healthRepo: any HealthPort
    package let webSocketClient: WebSocketClient
    package let settings: Settings

    package init(settings: Settings = .load()) {
        self.settings = settings

        let apiClient = APIClient(baseURL: settings.backendURL)
        let docRepo = APIDocumentRepository(client: apiClient)
        let searchRepo = APISearchRepository(client: apiClient)
        let healthRepo = APIHealthRepository(client: apiClient)

        self.documentService = DocumentService(docRepo: docRepo)
        self.searchService = SearchService(searchRepo: searchRepo)
        self.ingestionService = IngestionService(docRepo: docRepo)
        self.healthRepo = healthRepo
        self.webSocketClient = WebSocketClient(baseURL: settings.backendURL)
    }
}
