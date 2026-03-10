import XCTest
import Infrastructure

final class HTMLPreparerTests: XCTestCase {

    // MARK: - Full document detection

    func testDetectsFullDocumentWithDoctype() {
        let html = "<!DOCTYPE html><html><head></head><body><p>Hello</p></body></html>"
        XCTAssertTrue(isFullHTMLDocument(html))
    }

    func testDetectsFullDocumentWithHtmlTag() {
        let html = "<html><head></head><body><p>Hello</p></body></html>"
        XCTAssertTrue(isFullHTMLDocument(html))
    }

    func testDetectsFullDocumentCaseInsensitive() {
        let html = "<!doctype HTML><HTML><HEAD></HEAD><BODY></BODY></HTML>"
        XCTAssertTrue(isFullHTMLDocument(html))
    }

    func testDetectsFullDocumentWithChunkAnchorsBeforeDoctype() {
        // Backend injects chunk anchors before the doctype — this is the real payload shape
        let html = "<span id=\"chunk-0\"></span><!DOCTYPE html><html><head></head><body></body></html>"
        XCTAssertTrue(isFullHTMLDocument(html), "Should detect full document even with chunk anchors prepended")
    }

    func testDetectsFragmentPreTag() {
        let html = "<pre>Some plain text content</pre>"
        XCTAssertFalse(isFullHTMLDocument(html))
    }

    func testDetectsFragmentParagraph() {
        let html = "<p>Just a paragraph</p>"
        XCTAssertFalse(isFullHTMLDocument(html))
    }

    func testDetectsFragmentWithChunkAnchorOnly() {
        // Fragment with chunk anchor but no </head>
        let html = "<span id=\"chunk-0\"></span><pre>text</pre>"
        XCTAssertFalse(isFullHTMLDocument(html))
    }

    // MARK: - CSS injection for full documents

    func testInjectsCSSBeforeClosingHead() {
        let html = "<!DOCTYPE html><html><head><title>Test</title></head><body></body></html>"
        let result = injectCortexCSS(into: html)
        XCTAssertTrue(result.contains("<style>"))
        let styleRange = result.range(of: "<style>")!
        let headRange = result.range(of: "</head>")!
        XCTAssertTrue(styleRange.lowerBound < headRange.lowerBound)
    }

    func testInjectsCSSIntoDocumentWithChunkAnchorsPrefix() {
        let html = "<span id=\"chunk-0\"></span><!DOCTYPE html><html><head></head><body><p>Content</p></body></html>"
        let result = injectCortexCSS(into: html)
        XCTAssertTrue(result.contains("<style>"))
        // Should only have one <!DOCTYPE
        let doctypeCount = result.components(separatedBy: "<!DOCTYPE").count - 1
        XCTAssertEqual(doctypeCount, 1)
    }

    // MARK: - Fragment wrapping

    func testWrapsFragmentInFullDocument() {
        let fragment = "<pre>Hello world</pre>"
        let result = wrapHTMLFragment(fragment)
        XCTAssertTrue(result.contains("<!DOCTYPE html>"))
        XCTAssertTrue(result.contains("<body>"))
        XCTAssertTrue(result.contains(fragment))
        XCTAssertTrue(result.contains("<style>"))
    }

    // MARK: - prepareHTML end-to-end

    func testPrepareHTMLWrapsFragment() {
        let fragment = "<pre>plain text</pre>"
        let result = prepareHTML(fragment)
        XCTAssertTrue(result.contains("<!DOCTYPE html>"))
        XCTAssertTrue(result.contains(fragment))
    }

    func testPrepareHTMLInjectsCSSIntoFullDocument() {
        let fullDoc = "<!DOCTYPE html><html><head></head><body><p>Content</p></body></html>"
        let result = prepareHTML(fullDoc)
        let doctypeCount = result.components(separatedBy: "<!DOCTYPE").count - 1
        XCTAssertEqual(doctypeCount, 1, "Should not double-wrap full documents")
        XCTAssertTrue(result.contains("<style>"))
    }

    func testPrepareHTMLHandlesChunkAnchorPrefixedDocument() {
        // This is the actual live backend payload shape
        let html = "<span id=\"chunk-0\"></span><!DOCTYPE html><html><head></head><body><p>Parsed content</p></body></html>"
        let result = prepareHTML(html)
        let doctypeCount = result.components(separatedBy: "<!DOCTYPE").count - 1
        XCTAssertEqual(doctypeCount, 1, "Should inject CSS, not re-wrap")
        XCTAssertTrue(result.contains("<style>"))
        XCTAssertTrue(result.contains("<span id=\"chunk-0\">"))
    }

    func testPrepareHTMLHandlesLeadingWhitespace() {
        let html = "  \n  <!DOCTYPE html><html><head></head><body></body></html>"
        let result = prepareHTML(html)
        let doctypeCount = result.components(separatedBy: "<!DOCTYPE").count - 1
        XCTAssertEqual(doctypeCount, 1)
    }
}
