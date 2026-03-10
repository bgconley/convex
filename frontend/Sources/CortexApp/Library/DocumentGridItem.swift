import SwiftUI
import Domain
import Infrastructure

struct DocumentGridItem: View {
    let document: Document
    let thumbnailLoader: ThumbnailLoader
    let onSelect: () -> Void
    let onToggleFavorite: () -> Void
    let onDelete: () -> Void

    @State private var thumbnail: NSImage?

    var body: some View {
        Button(action: onSelect) {
            VStack(spacing: 0) {
                thumbnailView
                    .frame(height: 160)
                    .frame(maxWidth: .infinity)
                    .clipped()

                VStack(alignment: .leading, spacing: 4) {
                    Text(document.title)
                        .font(.caption)
                        .fontWeight(.medium)
                        .lineLimit(2)
                        .truncationMode(.tail)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    HStack(spacing: 4) {
                        Image(systemName: document.fileType.iconName)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Text(document.fileType.displayName)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Spacer()
                        if document.isFavorite {
                            Image(systemName: "star.fill")
                                .font(.caption2)
                                .foregroundStyle(.yellow)
                        }
                    }
                }
                .padding(8)
            }
            .background(.background)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(.separator, lineWidth: 1)
            )
            .overlay {
                if document.status.isProcessing {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(.ultraThinMaterial)
                        .overlay {
                            VStack(spacing: 8) {
                                ProgressView()
                                Text(document.status.displayLabel)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                }
            }
        }
        .buttonStyle(.plain)
        .contextMenu {
            Button("Open") { onSelect() }
            Divider()
            Button {
                onToggleFavorite()
            } label: {
                Label(
                    document.isFavorite ? "Remove from Favorites" : "Add to Favorites",
                    systemImage: document.isFavorite ? "star.slash" : "star"
                )
            }
            Divider()
            Button(role: .destructive) {
                onDelete()
            } label: {
                Label("Delete", systemImage: "trash")
            }
        }
        .task {
            thumbnail = await thumbnailLoader.loadThumbnail(documentId: document.id)
        }
    }

    @ViewBuilder
    private var thumbnailView: some View {
        if let thumbnail {
            Image(nsImage: thumbnail)
                .resizable()
                .aspectRatio(contentMode: .fill)
        } else {
            Rectangle()
                .fill(.quaternary)
                .overlay {
                    Image(systemName: document.fileType.iconName)
                        .font(.system(size: 32))
                        .foregroundStyle(.secondary)
                }
        }
    }
}
