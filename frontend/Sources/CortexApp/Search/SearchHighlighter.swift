import SwiftUI

/// Parses backend `highlighted_snippet` containing `<mark>` tags and converts
/// to an `AttributedString` with bold + background color for matched terms.
struct SearchHighlighter {
    static func attributedSnippet(from html: String) -> AttributedString {
        var result = AttributedString()
        var remaining = html[...]

        while let markStart = remaining.range(of: "<mark>") {
            // Text before <mark>
            let plainText = String(remaining[remaining.startIndex..<markStart.lowerBound])
            if !plainText.isEmpty {
                result.append(AttributedString(plainText))
            }

            remaining = remaining[markStart.upperBound...]

            // Text inside <mark>...</mark>
            if let markEnd = remaining.range(of: "</mark>") {
                let matchedText = String(remaining[remaining.startIndex..<markEnd.lowerBound])
                var highlighted = AttributedString(matchedText)
                highlighted.font = .body.bold()
                highlighted.backgroundColor = .yellow.opacity(0.3)
                result.append(highlighted)
                remaining = remaining[markEnd.upperBound...]
            }
        }

        // Trailing text after last </mark>
        let trailing = String(remaining)
        if !trailing.isEmpty {
            result.append(AttributedString(trailing))
        }

        return result
    }
}
