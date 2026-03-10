import Domain
import Foundation

package actor SearchService {
    private let searchRepo: any SearchPort
    private var debounceTask: Task<Void, Never>?

    package init(searchRepo: any SearchPort) {
        self.searchRepo = searchRepo
    }

    package func search(query: String, topK: Int = 10, filters: SearchFilters? = nil) async throws -> SearchResponse {
        let request = SearchRequest(query: query, topK: topK, filters: filters)
        return try await searchRepo.search(request: request)
    }

    /// Debounced search — cancels previous pending search and waits before executing.
    package func debouncedSearch(
        query: String,
        topK: Int = 10,
        delayMs: UInt64 = 300,
        onResult: @Sendable @escaping (Result<SearchResponse, Error>) -> Void
    ) {
        debounceTask?.cancel()
        debounceTask = Task {
            do {
                try await Task.sleep(nanoseconds: delayMs * 1_000_000)
                guard !Task.isCancelled else { return }
                let result = try await search(query: query, topK: topK)
                onResult(.success(result))
            } catch is CancellationError {
                // Debounce cancelled — expected
            } catch {
                onResult(.failure(error))
            }
        }
    }
}
