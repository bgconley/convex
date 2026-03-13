import SwiftUI
import Domain

struct DocumentListRow: View {
    let document: Document

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: document.fileType.iconName)
                .foregroundStyle(.secondary)
            Text(document.title)
                .lineLimit(1)
            if document.status.isProcessing {
                ProgressView()
                    .controlSize(.mini)
            } else if document.status == .failed {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.red)
                    .help(Text(verbatim: document.errorMessage ?? "Processing failed"))
            }
            if document.isFavorite {
                Image(systemName: "star.fill")
                    .font(.caption2)
                    .foregroundStyle(.yellow)
            }
        }
        .draggable(document.id.uuidString)
    }
}
