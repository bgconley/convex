import SwiftUI
import WebKit
import AppKit
import Domain
import Infrastructure

struct HTMLDocumentView: View {
    let htmlContent: String
    let anchorId: String?
    var searchQuery: String = ""

    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        HTMLWebView(
            html: prepareHTML(htmlContent),
            anchorId: anchorId,
            searchQuery: searchQuery,
            colorScheme: colorScheme
        )
    }
}

struct HTMLWebView: NSViewRepresentable {
    let html: String
    let anchorId: String?
    var searchQuery: String = ""
    let colorScheme: ColorScheme

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeNSView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.navigationDelegate = context.coordinator
        context.coordinator.pendingAnchorId = anchorId
        context.coordinator.pendingSearchQuery = searchQuery
        context.coordinator.pendingColorScheme = colorScheme
        webView.loadHTMLString(html, baseURL: nil)
        context.coordinator.lastLoadedHTML = html
        context.coordinator.lastColorScheme = colorScheme
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
        let colorChanged = colorScheme != context.coordinator.lastColorScheme

        if anchorChanged {
            context.coordinator.lastScrolledAnchor = anchorId
        }
        if searchChanged {
            context.coordinator.lastSearchQuery = searchQuery
        }
        if colorChanged {
            context.coordinator.lastColorScheme = colorScheme
        }

        guard contentChanged || anchorChanged || searchChanged || colorChanged else { return }
        context.coordinator.pendingAnchorId = anchorId
        context.coordinator.pendingSearchQuery = searchQuery
        context.coordinator.pendingColorScheme = colorScheme

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
        var lastColorScheme: ColorScheme = .light
        var pendingAnchorId: String?
        var pendingSearchQuery: String = ""
        var pendingColorScheme: ColorScheme = .light

        func webView(_ webView: WKWebView, didFinish _: WKNavigation!) {
            applyNavigation(to: webView)
        }

        func applyNavigation(to webView: WKWebView) {
            applyTheme(to: webView)
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

        private func applyTheme(to webView: WKWebView) {
            if #available(macOS 13.0, *) {
                webView.underPageBackgroundColor = pendingColorScheme == .dark
                    ? NSColor(calibratedWhite: 0.11, alpha: 1.0)
                    : NSColor.white
            }

            let css = pendingColorScheme.runtimeViewerCSS.jsEscapedForLiteral
            let script = """
            (() => {
                let head = document.head;
                if (!head) {
                    head = document.createElement('head');
                    document.documentElement.insertBefore(head, document.body);
                }
                let style = document.getElementById('cortex-runtime-theme');
                if (!style) {
                    style = document.createElement('style');
                    style.id = 'cortex-runtime-theme';
                    head.appendChild(style);
                }
                style.textContent = '\(css)';
            })();
            """
            webView.evaluateJavaScript(script)
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

private extension ColorScheme {
    var runtimeViewerCSS: String {
        let palette = self == .dark
            ? (
                background: "#1d1d1f",
                foreground: "#f5f5f7",
                secondaryBackground: "#2d2d2f",
                border: "#48484a",
                link: "#2997ff",
                mark: "#ffd966"
            )
            : (
                background: "#ffffff",
                foreground: "#1d1d1f",
                secondaryBackground: "#f5f5f7",
                border: "#d1d1d6",
                link: "#0066cc",
                mark: "#ffe58f"
            )

        return """
        :root { color-scheme: \(self == .dark ? "dark" : "light") !important; }
        html, body {
            background: \(palette.background) !important;
            color: \(palette.foreground) !important;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif !important;
            font-size: 15px !important;
            line-height: 1.6 !important;
            margin: 0 auto !important;
            padding: 24px !important;
        }
        body, p, div, span, li, td, th, h1, h2, h3, h4, h5, h6, blockquote, font {
            color: inherit !important;
        }
        p, div, span, li, td, th, blockquote {
            background-color: transparent !important;
        }
        a {
            color: \(palette.link) !important;
        }
        table, th, td {
            border-color: \(palette.border) !important;
        }
        th {
            background: \(palette.secondaryBackground) !important;
        }
        pre, code {
            color: \(palette.foreground) !important;
            background: \(palette.secondaryBackground) !important;
        }
        blockquote {
            border-left-color: \(palette.border) !important;
        }
        mark {
            background: \(palette.mark) !important;
            color: #1d1d1f !important;
        }
        """
    }
}
