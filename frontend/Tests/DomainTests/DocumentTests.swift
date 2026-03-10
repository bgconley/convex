import XCTest
@testable import Domain

final class DocumentTests: XCTestCase {
    func testFileTypeIcons() {
        XCTAssertEqual(FileType.pdf.iconName, "doc.richtext")
        XCTAssertEqual(FileType.markdown.iconName, "doc.text")
        XCTAssertEqual(FileType.xlsx.iconName, "tablecells")
    }

    func testProcessingStatusLifecycle() {
        let processingStatuses: [ProcessingStatus] = [
            .uploading, .stored, .parsing, .parsed,
            .chunking, .chunked, .embedding, .embedded,
        ]
        for status in processingStatuses {
            XCTAssertTrue(status.isProcessing, "\(status) should be processing")
        }
        XCTAssertFalse(ProcessingStatus.ready.isProcessing)
        XCTAssertFalse(ProcessingStatus.failed.isProcessing)
    }
}
