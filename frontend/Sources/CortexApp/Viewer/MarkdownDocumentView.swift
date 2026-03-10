import SwiftUI
import WebKit
import Infrastructure

struct MarkdownDocumentView: NSViewRepresentable {
    let markdownSource: String
    let renderer: MarkdownRenderer

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.setValue(false, forKey: "drawsBackground")
        let html = renderer.renderHTML(from: markdownSource)
        webView.loadHTMLString(html, baseURL: nil)
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        let html = renderer.renderHTML(from: markdownSource)
        webView.loadHTMLString(html, baseURL: nil)
    }
}
