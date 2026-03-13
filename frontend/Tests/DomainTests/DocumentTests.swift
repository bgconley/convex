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

    func testViewerRepresentationPolicy() {
        XCTAssertFalse(FileType.markdown.prefersOriginalFidelityView)

        for fileType in [FileType.pdf, .docx, .xlsx, .txt, .png, .jpg, .tiff] {
            XCTAssertTrue(fileType.prefersOriginalFidelityView, "\(fileType) should prefer original fidelity")
        }

        XCTAssertTrue(FileType.docx.supportsStructuredFallbackView)
        XCTAssertTrue(FileType.xlsx.supportsStructuredFallbackView)
        XCTAssertFalse(FileType.pdf.supportsStructuredFallbackView)
        XCTAssertFalse(FileType.txt.supportsStructuredFallbackView)
        XCTAssertFalse(FileType.markdown.supportsStructuredFallbackView)
    }
}
