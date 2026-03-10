import SwiftUI
import WebKit
import Domain
import Infrastructure

struct SpreadsheetView: View {
    let htmlContent: String
    let originalURL: URL
    let anchorId: String?

    @State private var viewMode: ViewRepresentation = .structured
    @State private var sheetNames: [String] = []
    @State private var selectedSheet: String?

    enum ViewRepresentation: String, CaseIterable {
        case structured = "Structured"
        case original = "Original"
    }

    var body: some View {
        Group {
            switch viewMode {
            case .structured:
                SpreadsheetWebView(
                    html: prepareHTML(htmlContent),
                    selectedSheet: selectedSheet,
                    anchorId: anchorId,
                    onSheetsDetected: { names in
                        sheetNames = names
                        if selectedSheet == nil {
                            selectedSheet = names.first
                        }
                    },
                    onActiveSheetDetected: { sheetName in
                        selectedSheet = sheetName
                    }
                )
            case .original:
                QuickLookView(url: originalURL)
            }
        }
        .toolbar {
            ToolbarItemGroup(placement: .automatic) {
                if sheetNames.count > 1 && viewMode == .structured {
                    Picker("Sheet", selection: sheetTabBinding) {
                        ForEach(sheetNames, id: \.self) { name in
                            Text(name).tag(name)
                        }
                    }
                    .help("Select sheet")
                }

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

    private var sheetTabBinding: Binding<String> {
        Binding(
            get: { selectedSheet ?? "" },
            set: { selectedSheet = $0 }
        )
    }
}

struct SpreadsheetWebView: NSViewRepresentable {
    let html: String
    let selectedSheet: String?
    let anchorId: String?
    let onSheetsDetected: ([String]) -> Void
    let onActiveSheetDetected: (String) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(anchorId: anchorId, onSheetsDetected: onSheetsDetected, onActiveSheetDetected: onActiveSheetDetected)
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.userContentController.add(context.coordinator, name: "sheetDetector")
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.setValue(false, forKey: "drawsBackground")
        webView.navigationDelegate = context.coordinator
        context.coordinator.webView = webView
        webView.loadHTMLString(html, baseURL: nil)
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        guard let sheet = selectedSheet else { return }
        let escapedSheet = sheet.replacingOccurrences(of: "'", with: "\\'")
            .replacingOccurrences(of: "\\", with: "\\\\")
        webView.evaluateJavaScript("""
            (function() {
                var sections = document.querySelectorAll('.cortex-sheet-section');
                sections.forEach(function(s) {
                    s.style.display = (s.dataset.sheetName === '\(escapedSheet)') ? '' : 'none';
                });
            })();
            """)
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        let anchorId: String?
        let onSheetsDetected: ([String]) -> Void
        let onActiveSheetDetected: (String) -> Void
        weak var webView: WKWebView?

        init(anchorId: String?, onSheetsDetected: @escaping ([String]) -> Void, onActiveSheetDetected: @escaping (String) -> Void) {
            self.anchorId = anchorId
            self.onSheetsDetected = onSheetsDetected
            self.onActiveSheetDetected = onActiveSheetDetected
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            webView.evaluateJavaScript(Self.detectAndWrapSheetsJS)
        }

        func userContentController(
            _ userContentController: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            if let names = message.body as? [String] {
                DispatchQueue.main.async {
                    self.onSheetsDetected(names)
                }
                // If we have an anchor, find which sheet contains it, show that sheet, and scroll
                if let anchorId, let webView, !names.isEmpty {
                    let escaped = anchorId.replacingOccurrences(of: "'", with: "\\'")
                    let js = """
                    (function() {
                        var el = document.getElementById('\(escaped)');
                        if (!el) return null;
                        var section = el.closest('.cortex-sheet-section');
                        if (!section) return null;
                        var sheetName = section.dataset.sheetName;
                        // Show the containing sheet, hide others
                        document.querySelectorAll('.cortex-sheet-section').forEach(function(s) {
                            s.style.display = (s.dataset.sheetName === sheetName) ? '' : 'none';
                        });
                        el.scrollIntoView({behavior: 'smooth'});
                        return sheetName;
                    })();
                    """
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { [weak self] in
                        webView.evaluateJavaScript(js) { result, _ in
                            if let sheetName = result as? String {
                                DispatchQueue.main.async {
                                    self?.onActiveSheetDetected(sheetName)
                                }
                            }
                        }
                    }
                }
            }
        }

        /// JavaScript that detects sheet boundaries in Docling XLSX HTML and wraps
        /// each sheet in a togglable <div>. Detection strategy (in priority order):
        /// 1. <h2> elements (Docling heading-delimited sheets)
        /// 2. <table> elements with <caption> children
        /// 3. Multiple top-level <table> elements (numbered as "Sheet 1", "Sheet 2", ...)
        private static let detectAndWrapSheetsJS = """
        (function() {
            var body = document.body;
            if (!body) { window.webkit.messageHandlers.sheetDetector.postMessage([]); return; }

            var names = [];

            // Strategy 1: h2-delimited sections
            var h2s = body.querySelectorAll('h2');
            if (h2s.length > 1) {
                for (var i = 0; i < h2s.length; i++) {
                    var name = h2s[i].textContent.trim();
                    names.push(name);
                    var div = document.createElement('div');
                    div.className = 'cortex-sheet-section';
                    div.dataset.sheetName = name;
                    h2s[i].parentNode.insertBefore(div, h2s[i]);
                    div.appendChild(h2s[i]);
                    var next = div.nextSibling;
                    while (next && !(next.nodeType === 1 && next.tagName === 'H2')) {
                        var toMove = next;
                        next = next.nextSibling;
                        div.appendChild(toMove);
                    }
                }
                window.webkit.messageHandlers.sheetDetector.postMessage(names);
                return;
            }

            // Strategy 2: tables with captions
            var tables = body.querySelectorAll('table');
            var captioned = [];
            tables.forEach(function(t) {
                var cap = t.querySelector('caption');
                if (cap) captioned.push({ table: t, name: cap.textContent.trim() });
            });
            if (captioned.length > 1) {
                captioned.forEach(function(c) {
                    names.push(c.name);
                    var div = document.createElement('div');
                    div.className = 'cortex-sheet-section';
                    div.dataset.sheetName = c.name;
                    c.table.parentNode.insertBefore(div, c.table);
                    div.appendChild(c.table);
                });
                window.webkit.messageHandlers.sheetDetector.postMessage(names);
                return;
            }

            // Strategy 3: multiple top-level tables — number them as Sheet 1, Sheet 2, etc.
            if (tables.length > 1) {
                tables.forEach(function(t, idx) {
                    var name = 'Sheet ' + (idx + 1);
                    names.push(name);
                    var div = document.createElement('div');
                    div.className = 'cortex-sheet-section';
                    div.dataset.sheetName = name;
                    t.parentNode.insertBefore(div, t);
                    div.appendChild(t);
                });
                window.webkit.messageHandlers.sheetDetector.postMessage(names);
                return;
            }

            // Single table or no tables — no sheet tabs needed
            window.webkit.messageHandlers.sheetDetector.postMessage([]);
        })();
        """
    }
}
