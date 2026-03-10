import XCTest
@testable import Infrastructure

final class APIClientTests: XCTestCase {
    func testAPIClientInitializes() {
        let client = APIClient(baseURL: URL(string: "http://localhost:8090/api/v1")!)
        XCTAssertNotNil(client)
    }
}
