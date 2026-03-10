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
}

final class SearchServiceTests: XCTestCase {
    func testSearchServiceCallsPort() async throws {
        let fakeRepo = FakeSearchRepo()
        let service = SearchService(searchRepo: fakeRepo)
        let response = try await service.search(query: "test query")
        XCTAssertEqual(response.query, "test query")
        XCTAssertTrue(response.results.isEmpty)
    }
}
