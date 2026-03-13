import Foundation

/// Ensures HTML content has proper Cortex styling. If the content contains
/// a <head> element (full document from Docling), CSS is injected into it.
/// Otherwise the content is wrapped in a complete HTML shell.
package func prepareHTML(_ content: String) -> String {
    let trimmed = content.trimmingCharacters(in: .whitespacesAndNewlines)
    if isFullHTMLDocument(trimmed) {
        return injectCortexCSS(into: trimmed)
    } else {
        return wrapHTMLFragment(trimmed)
    }
}

/// A full HTML document is detected by the presence of </head> anywhere in the
/// content. This works even when the backend prepends chunk anchors before the
/// doctype (e.g. `<span id="chunk-0"></span><!DOCTYPE html>...`).
package func isFullHTMLDocument(_ content: String) -> Bool {
    content.range(of: "</head>", options: .caseInsensitive) != nil
}

package func injectCortexCSS(into html: String) -> String {
    let styleTag = "<style>\(cortexCSS)</style>"
    if let range = html.range(of: "</head>", options: .caseInsensitive) {
        var result = html
        result.insert(contentsOf: styleTag, at: range.lowerBound)
        return result
    }
    // Shouldn't reach here given isFullHTMLDocument checks for </head>,
    // but handle gracefully
    return styleTag + html
}

package func wrapHTMLFragment(_ body: String) -> String {
    """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
    \(cortexCSS)
    </style>
    </head>
    <body>
    \(body)
    </body>
    </html>
    """
}

package let cortexCSS = """
:root { color-scheme: light dark; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
    font-size: 15px;
    line-height: 1.6;
    max-width: 900px;
    margin: 0 auto;
    padding: 24px;
    color: #1d1d1f;
    background: #ffffff;
}
a { color: #0066cc; text-decoration: none; }
a:hover { text-decoration: underline; }
@media (prefers-color-scheme: dark) {
    body { color: #f5f5f7; background: #1d1d1f; }
    a { color: #2997ff; }
    code, pre { background: #2d2d2f; }
    table, th, td { border-color: #48484a; }
    blockquote { border-left-color: #48484a; color: #98989d; }
    hr { border-top-color: #48484a; }
}
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #d1d1d6; padding: 8px 12px; text-align: left; }
th { font-weight: 600; }
img { max-width: 100%; height: auto; }
pre { overflow-x: auto; padding: 16px; background: #f5f5f7; border-radius: 8px; }
code { font-family: "SF Mono", Menlo, monospace; font-size: 0.9em; }
blockquote { margin: 1em 0; padding: 0.5em 1em; border-left: 4px solid #d1d1d6; color: #86868b; }
hr { border: none; border-top: 1px solid #d1d1d6; margin: 2em 0; }
"""
