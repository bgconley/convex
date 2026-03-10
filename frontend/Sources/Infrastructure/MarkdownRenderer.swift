import Foundation
import Markdown

package struct MarkdownRenderer: Sendable {
    package init() {}

    package func renderHTML(from markdownSource: String) -> String {
        let document = Document(parsing: markdownSource)
        let bodyHTML = HTMLFormatter.format(document)

        return """
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
        \(Self.css)
        </style>
        </head>
        <body>
        \(bodyHTML)
        </body>
        </html>
        """
    }

    private static let css = """
    :root {
        color-scheme: light dark;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
        font-size: 15px;
        line-height: 1.6;
        max-width: 800px;
        margin: 0 auto;
        padding: 24px;
        color: #1d1d1f;
        background: #ffffff;
    }
    @media (prefers-color-scheme: dark) {
        body {
            color: #f5f5f7;
            background: #1d1d1f;
        }
        a { color: #2997ff; }
        code { background: #2d2d2f; }
        pre { background: #2d2d2f; }
        blockquote { border-left-color: #48484a; }
        table, th, td { border-color: #48484a; }
    }
    h1, h2, h3, h4, h5, h6 {
        margin-top: 1.4em;
        margin-bottom: 0.6em;
        font-weight: 600;
    }
    h1 { font-size: 2em; }
    h2 { font-size: 1.5em; }
    h3 { font-size: 1.25em; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
    code {
        font-family: "SF Mono", Menlo, Monaco, monospace;
        font-size: 0.9em;
        background: #f5f5f7;
        padding: 2px 6px;
        border-radius: 4px;
    }
    pre {
        background: #f5f5f7;
        padding: 16px;
        border-radius: 8px;
        overflow-x: auto;
    }
    pre code {
        background: none;
        padding: 0;
    }
    blockquote {
        margin: 1em 0;
        padding: 0.5em 1em;
        border-left: 4px solid #d1d1d6;
        color: #86868b;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 1em 0;
    }
    th, td {
        border: 1px solid #d1d1d6;
        padding: 8px 12px;
        text-align: left;
    }
    th { font-weight: 600; }
    img { max-width: 100%; height: auto; border-radius: 8px; }
    hr { border: none; border-top: 1px solid #d1d1d6; margin: 2em 0; }
    ul, ol { padding-left: 1.5em; }
    li { margin: 0.25em 0; }
    """
}
