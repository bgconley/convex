import SwiftUI
import UniformTypeIdentifiers

struct DocumentDropZone: View {
    let onFilesDropped: ([URL]) -> Void
    @State private var isTargeted = false

    static let supportedTypes: [UTType] = [
        .pdf, .plainText,
        UTType(filenameExtension: "md") ?? .plainText,
        UTType("org.openxmlformats.wordprocessingml.document") ?? .data,
        UTType("org.openxmlformats.spreadsheetml.sheet") ?? .data,
        .png, .jpeg, .tiff,
    ]

    static let supportedExtensions: Set<String> = [
        "pdf", "txt", "md", "markdown",
        "docx", "xlsx",
        "png", "jpg", "jpeg", "tiff", "tif",
    ]

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "arrow.down.doc")
                .font(.system(size: 48))
                .foregroundStyle(isTargeted ? Color.accentColor : Color.secondary)

            Text("Drop files to import")
                .font(.title2)
                .foregroundStyle(isTargeted ? Color.primary : Color.secondary)

            Text("PDF, Markdown, Word, Excel, Text, Images")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background {
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(
                    isTargeted ? Color.accentColor : Color.gray.opacity(0.3),
                    style: StrokeStyle(lineWidth: 2, dash: [8, 4])
                )
        }
        .padding(24)
        .onDrop(of: [.fileURL], isTargeted: $isTargeted) { providers in
            handleDrop(providers)
        }
    }

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        let validExtensions = Self.supportedExtensions
        Task { @MainActor in
            var urls: [URL] = []
            for provider in providers {
                guard provider.canLoadObject(ofClass: URL.self) else { continue }
                if let url = await loadURL(from: provider),
                   validExtensions.contains(url.pathExtension.lowercased()) {
                    urls.append(url)
                }
            }
            if !urls.isEmpty {
                onFilesDropped(urls)
            }
        }
        return true
    }

    private func loadURL(from provider: NSItemProvider) async -> URL? {
        await withCheckedContinuation { continuation in
            _ = provider.loadObject(ofClass: URL.self) { url, _ in
                continuation.resume(returning: url)
            }
        }
    }
}
