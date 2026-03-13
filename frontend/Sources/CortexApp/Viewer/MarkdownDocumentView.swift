import SwiftUI
import Infrastructure

struct MarkdownDocumentView: View {
    let markdownSource: String
    let renderer: MarkdownRenderer
    var anchorId: String?
    var searchQuery: String = ""

    var body: some View {
        HTMLWebView(
            html: renderer.renderHTML(from: markdownSource),
            anchorId: anchorId,
            searchQuery: searchQuery
        )
    }
}
