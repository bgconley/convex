import XCTest
import Domain
@testable import AppCore

/// Protocol test double — no mocking framework needed.
/// @unchecked Sendable is acceptable in test code for mutable recording state.
final class FakeSearchRepo: SearchPort, @unchecked Sendable {
    private(set) var lastRequest: SearchRequest?

    func search(request: SearchRequest) async throws -> SearchResponse {
        lastRequest = request
        return SearchResponse(
            query: request.query,
            results: [],
            totalCandidates: 0,
            searchTimeMs: 1.0
        )
    }

    func searchDocuments(request: SearchRequest) async throws -> DocumentSearchResponse {
        lastRequest = request
        return DocumentSearchResponse(
            query: request.query,
            results: [],
            totalDocuments: 0,
            searchTimeMs: 1.0
        )
    }

    func suggestions(query: String, limit: Int) async throws -> SearchSuggestionsResponse {
        SearchSuggestionsResponse(
            query: query,
            recentSearches: [],
            entities: [],
            documents: []
        )
    }
}

final class SearchServiceTests: XCTestCase {
    func testSearchServiceCallsPort() async throws {
        let fakeRepo = FakeSearchRepo()
        let service = SearchService(searchRepo: fakeRepo)
        let response = try await service.search(query: "test query")
        XCTAssertEqual(response.query, "test query")
        XCTAssertTrue(response.results.isEmpty)
    }

    func testCancelPendingSearchPreventsExecution() async throws {
        let fakeRepo = FakeSearchRepo()
        let service = SearchService(searchRepo: fakeRepo)
        let expectation = XCTestExpectation(description: "debounce callback")
        expectation.isInverted = true // Should NOT be fulfilled

        await service.debouncedSearch(query: "should be cancelled", delayMs: 100) { _ in
            expectation.fulfill()
        }
        await service.cancelPendingSearch()

        // Wait longer than the debounce delay to confirm it didn't fire
        await fulfillment(of: [expectation], timeout: 0.3)
    }
}
