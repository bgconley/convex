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

                if !item.entities.isEmpty {
                    HStack(spacing: 4) {
                        ForEach(Array(item.entities.prefix(5).enumerated()), id: \.offset) { _, mention in
                            EntityChipView(name: mention.name, entityType: mention.entityType)
                        }
                    }
                }

                HStack(spacing: 12) {
                    scoreLabel
                        .help(Text(verbatim: scoreTooltip))

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

    private var scoreLabel: some View {
        Text(String(format: "%.2f", item.score))
            .font(.caption2)
            .monospacedDigit()
            .foregroundStyle(.secondary)
    }

    private var scoreTooltip: String {
        let bd = item.scoreBreakdown
        var parts: [String] = []
        if let v = bd.vectorScore { parts.append(String(format: "Vector: %.3f", v)) }
        if let b = bd.bm25Score { parts.append(String(format: "BM25: %.3f", b)) }
        if let r = bd.rerankScore { parts.append(String(format: "Rerank: %.2f", r)) }
        return parts.isEmpty ? "Score: \(String(format: "%.4f", item.score))" : parts.joined(separator: "\n")
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

struct DocumentSearchResultRow: View {
    let item: DocumentSearchResultItem
    let isSelected: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: iconName(for: item.documentType))
                .font(.title3)
                .foregroundStyle(.secondary)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(item.documentTitle)
                        .font(.headline)
                        .lineLimit(1)
                    Spacer()
                    Text("\(item.chunkCount) match\(item.chunkCount == 1 ? "" : "es")")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }

                if let section = item.bestChunkSection {
                    Text(section)
                        .font(.caption)
                        .foregroundStyle(.blue)
                        .lineLimit(1)
                }

                Text(SearchHighlighter.attributedSnippet(from: item.bestChunkSnippet))
                    .font(.callout)
                    .lineLimit(3)
                    .foregroundStyle(.primary)

                HStack(spacing: 12) {
                    Text(String(format: "%.2f", item.score))
                        .font(.caption2)
                        .monospacedDigit()
                        .foregroundStyle(.secondary)
                        .help(Text(verbatim: docScoreTooltip))

                    if let page = item.bestChunkPage {
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

    private var docScoreTooltip: String {
        let bd = item.scoreBreakdown
        var parts: [String] = []
        if let v = bd.vectorScore { parts.append(String(format: "Vector: %.3f", v)) }
        if let b = bd.bm25Score { parts.append(String(format: "BM25: %.3f", b)) }
        if let r = bd.rerankScore { parts.append(String(format: "Rerank: %.2f", r)) }
        return parts.isEmpty ? "Score: \(String(format: "%.4f", item.score))" : parts.joined(separator: "\n")
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
