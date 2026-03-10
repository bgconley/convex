import SwiftUI
import WebKit
import Domain
import Infrastructure

struct HTMLDocumentView: View {
    let htmlContent: String
    let originalURL: URL
    let anchorId: String?

    @State private var viewMode: ViewRepresentation = .structured

    enum ViewRepresentation: String, CaseIterable {
        case structured = "Structured"
        case original = "Original"
    }

    var body: some View {
        Group {
            switch viewMode {
            case .structured:
                HTMLWebView(html: prepareHTML(htmlContent), anchorId: anchorId)
            case .original:
                QuickLookView(url: originalURL)
            }
        }
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Picker("View", selection: $viewMode) {
                    ForEach(ViewRepresentation.allCases, id: \.self) { mode in
                        Text(mode.rawValue).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .help("Toggle Structured / Original view")
            }
        }
    }
}

struct HTMLWebView: NSViewRepresentable {
    let html: String
    let anchorId: String?

    func makeNSView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.setValue(false, forKey: "drawsBackground")
        webView.loadHTMLString(html, baseURL: nil)
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        webView.loadHTMLString(html, baseURL: nil)
        if let anchorId {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                webView.evaluateJavaScript(
                    "document.getElementById('\(anchorId)')?.scrollIntoView({behavior:'smooth'})"
                )
            }
        }
    }
}
