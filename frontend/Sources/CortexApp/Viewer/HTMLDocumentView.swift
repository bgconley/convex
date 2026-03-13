import SwiftUI
import WebKit
import Domain
import Infrastructure

struct HTMLDocumentView: View {
    let htmlContent: String
    let originalURL: URL?
    let anchorId: String?
    var searchQuery: String = ""

    @State private var viewMode: ViewRepresentation = .structured

    enum ViewRepresentation: String, CaseIterable {
        case structured = "Structured"
        case original = "Original"
    }

    var body: some View {
        Group {
            switch viewMode {
            case .structured:
                HTMLWebView(
                    html: prepareHTML(htmlContent),
                    anchorId: anchorId,
                    searchQuery: searchQuery
                )
            case .original:
                if let originalURL {
                    QuickLookView(url: originalURL)
                } else {
                    ContentUnavailableView(
                        "Original file unavailable",
                        systemImage: "doc.badge.exclamationmark",
                        description: Text("Structured view is still available.")
                    )
                }
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
    var searchQuery: String = ""

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeNSView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.setValue(false, forKey: "drawsBackground")
        webView.navigationDelegate = context.coordinator
        context.coordinator.pendingAnchorId = anchorId
        context.coordinator.pendingSearchQuery = searchQuery
        webView.loadHTMLString(html, baseURL: nil)
        context.coordinator.lastLoadedHTML = html
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        let contentChanged = context.coordinator.lastLoadedHTML != html
        if contentChanged {
            webView.loadHTMLString(html, baseURL: nil)
            context.coordinator.lastLoadedHTML = html
        }

        let anchorChanged = anchorId != context.coordinator.lastScrolledAnchor
        let searchChanged = searchQuery != context.coordinator.lastSearchQuery

        if anchorChanged {
            context.coordinator.lastScrolledAnchor = anchorId
        }
        if searchChanged {
            context.coordinator.lastSearchQuery = searchQuery
        }

        guard contentChanged || anchorChanged || searchChanged else { return }
        context.coordinator.pendingAnchorId = anchorId
        context.coordinator.pendingSearchQuery = searchQuery

        // When the HTML changed we wait for WKWebView didFinishNavigation before
        // applying anchor scroll/find. For pure state changes we can apply now.
        if !contentChanged {
            context.coordinator.applyNavigation(to: webView)
        }
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var lastLoadedHTML: String?
        var lastScrolledAnchor: String?
        var lastSearchQuery: String = ""
        var pendingAnchorId: String?
        var pendingSearchQuery: String = ""

        func webView(_ webView: WKWebView, didFinish _: WKNavigation!) {
            applyNavigation(to: webView)
        }

        func applyNavigation(to webView: WKWebView) {
            webView.evaluateJavaScript("window.getSelection()?.removeAllRanges();")

            if let anchorId = pendingAnchorId, !anchorId.isEmpty {
                webView.evaluateJavaScript(
                    "document.getElementById('\(anchorId.jsEscapedForLiteral)')?.scrollIntoView({behavior:'smooth', block:'center'})"
                )
            }

            let trimmedQuery = pendingSearchQuery.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmedQuery.isEmpty {
                webView.evaluateJavaScript(
                    "window.find('\(trimmedQuery.jsEscapedForLiteral)', false, false, true, false, true, false)"
                )
            }
        }
    }
}

private extension String {
    var jsEscapedForLiteral: String {
        replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "'", with: "\\'")
            .replacingOccurrences(of: "\n", with: "\\n")
            .replacingOccurrences(of: "\r", with: "")
    }
}
