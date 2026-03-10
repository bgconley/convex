import SwiftUI
import Domain

struct SearchResultRow: View {
    let item: SearchResultItem
    let isSelected: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: iconName(for: item.documentType))
                .font(.title3)
                .foregroundStyle(.secondary)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 4) {
                Text(item.documentTitle)
                    .font(.headline)
                    .lineLimit(1)

                if let section = item.sectionHeading {
                    Text(section)
                        .font(.caption)
                        .foregroundStyle(.blue)
                        .lineLimit(1)
                }

                Text(SearchHighlighter.attributedSnippet(from: item.highlightedSnippet))
                    .font(.callout)
                    .lineLimit(3)
                    .foregroundStyle(.primary)

                HStack(spacing: 12) {
                    Text(String(format: "%.1f%%", item.score * 100))
                        .font(.caption2)
                        .monospacedDigit()
                        .foregroundStyle(.secondary)

                    if let page = item.pageNumber {
                        Text("p. \(page)")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding(.vertical, 6)
        .padding(.horizontal, 12)
        .background(isSelected ? Color.accentColor.opacity(0.15) : Color.clear)
        .contentShape(Rectangle())
    }

    private func iconName(for docType: String) -> String {
        switch docType {
        case "pdf": "doc.richtext"
        case "markdown": "doc.text"
        case "docx": "doc.fill"
        case "xlsx": "tablecells"
        case "txt": "doc.plaintext"
        case "png", "jpg", "tiff": "photo"
        default: "doc"
        }
    }
}
