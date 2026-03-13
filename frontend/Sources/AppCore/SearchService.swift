import Domain
import Foundation

package actor SearchService {
    private let searchRepo: any SearchPort
    private var debounceTask: Task<Void, Never>?

    package init(searchRepo: any SearchPort) {
        self.searchRepo = searchRepo
    }

    package func search(
        query: String,
        topK: Int = 10,
        filters: SearchFilters? = nil,
        rerank: Bool = true,
        includeGraph: Bool = true
    ) async throws -> SearchResponse {
        var request = SearchRequest(query: query, topK: topK, filters: filters)
        request.rerank = rerank
        request.includeGraph = includeGraph
        return try await searchRepo.search(request: request)
    }

    package func searchDocuments(
        query: String,
        topK: Int = 10,
        filters: SearchFilters? = nil,
        rerank: Bool = true,
        includeGraph: Bool = true
    ) async throws -> DocumentSearchResponse {
        var request = SearchRequest(query: query, topK: topK, filters: filters)
        request.rerank = rerank
        request.includeGraph = includeGraph
        return try await searchRepo.searchDocuments(request: request)
    }

    package func debouncedSearchDocuments(
        query: String,
        topK: Int = 10,
        filters: SearchFilters? = nil,
        rerank: Bool = true,
        includeGraph: Bool = true,
        delayMs: UInt64 = 300,
        onResult: @Sendable @escaping (Result<DocumentSearchResponse, Error>) -> Void
    ) {
        debounceTask?.cancel()
        debounceTask = Task {
            do {
                try await Task.sleep(nanoseconds: delayMs * 1_000_000)
                guard !Task.isCancelled else { return }
                let result = try await searchDocuments(query: query, topK: topK, filters: filters, rerank: rerank, includeGraph: includeGraph)
                onResult(.success(result))
            } catch is CancellationError {
                // Debounce cancelled — expected
            } catch {
                onResult(.failure(error))
            }
        }
    }

    package func suggestions(query: String, limit: Int = 5) async throws -> SearchSuggestionsResponse {
        try await searchRepo.suggestions(query: query, limit: limit)
    }

    package func cancelPendingSearch() {
        debounceTask?.cancel()
        debounceTask = nil
    }

    /// Debounced search — cancels previous pending search and waits before executing.
    package func debouncedSearch(
        query: String,
        topK: Int = 10,
        filters: SearchFilters? = nil,
        rerank: Bool = true,
        includeGraph: Bool = true,
        delayMs: UInt64 = 300,
        onResult: @Sendable @escaping (Result<SearchResponse, Error>) -> Void
    ) {
        debounceTask?.cancel()
        debounceTask = Task {
            do {
                try await Task.sleep(nanoseconds: delayMs * 1_000_000)
                guard !Task.isCancelled else { return }
                let result = try await search(query: query, topK: topK, filters: filters, rerank: rerank, includeGraph: includeGraph)
                onResult(.success(result))
            } catch is CancellationError {
                // Debounce cancelled — expected
            } catch {
                onResult(.failure(error))
            }
        }
    }
}
