import SwiftUI
import Domain
import AppCore

struct ImportProgressView: View {
    let fileURLs: [URL]
    let ingestionService: IngestionService
    let documentService: DocumentService
    let onDismiss: () -> Void

    @State private var fileStates: [FileImportState] = []

    private var allTerminal: Bool {
        guard !fileStates.isEmpty else { return false }
        return fileStates.allSatisfy(\.phase.isTerminal)
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Importing \(fileURLs.count) file\(fileURLs.count == 1 ? "" : "s")")
                    .font(.headline)
                Spacer()
                if !allTerminal {
                    ProgressView()
                        .controlSize(.small)
                }
            }
            .padding()

            Divider()

            List(fileStates) { state in
                HStack(spacing: 12) {
                    statusIcon(for: state.phase)
                        .frame(width: 20)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(state.filename)
                            .font(.body)
                            .lineLimit(1)
                        statusLabel(for: state)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    if case .processing(let status) = state.phase, status.isProcessing {
                        ProgressView()
                            .controlSize(.small)
                    }
                }
                .padding(.vertical, 2)
            }

            Divider()

            HStack {
                Spacer()
                Button("Done") {
                    onDismiss()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(!allTerminal)
                .padding()
            }
        }
        .frame(width: 450, height: 350)
        .interactiveDismissDisabled(!allTerminal)
        .task {
            await runImports()
        }
    }

    // MARK: - Import orchestration

    private func runImports() async {
        fileStates = fileURLs.map { url in
            FileImportState(id: UUID(), filename: url.lastPathComponent, fileURL: url, phase: .pending)
        }

        await withTaskGroup(of: Void.self) { group in
            for index in fileStates.indices {
                group.addTask {
                    await uploadAndTrack(index: index)
                }
            }
        }
    }

    private func uploadAndTrack(index: Int) async {
        let url = fileStates[index].fileURL

        await MainActor.run {
            fileStates[index].phase = .uploading
        }

        do {
            let response = try await ingestionService.uploadFile(at: url)

            if response.isDuplicate {
                await MainActor.run {
                    fileStates[index].phase = .duplicate
                }
                return
            }

            await MainActor.run {
                fileStates[index].phase = .processing(.stored)
                fileStates[index].documentId = response.id
            }

            await pollProcessingStatus(index: index, documentId: response.id)

        } catch {
            await MainActor.run {
                fileStates[index].phase = .failed(error.localizedDescription)
            }
        }
    }

    private func pollProcessingStatus(index: Int, documentId: UUID) async {
        var consecutiveFailures = 0
        while !Task.isCancelled {
            try? await Task.sleep(for: .seconds(1))
            do {
                let doc = try await documentService.get(id: documentId)
                consecutiveFailures = 0
                await MainActor.run {
                    fileStates[index].phase = .processing(doc.status)
                }
                if !doc.status.isProcessing {
                    return
                }
            } catch {
                consecutiveFailures += 1
                if consecutiveFailures >= 10 {
                    await MainActor.run {
                        fileStates[index].phase = .failed("Lost connection to server")
                    }
                    return
                }
            }
        }
    }

    // MARK: - Display helpers

    @ViewBuilder
    private func statusIcon(for phase: ImportPhase) -> some View {
        switch phase {
        case .pending:
            Image(systemName: "clock")
                .foregroundStyle(.tertiary)
        case .uploading:
            Image(systemName: "arrow.up.circle")
                .foregroundStyle(.blue)
        case .processing(let status):
            if status == .ready {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(.green)
            } else if status == .failed {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.red)
            } else {
                Image(systemName: "gearshape.2")
                    .foregroundStyle(.orange)
            }
        case .duplicate:
            Image(systemName: "arrow.triangle.2.circlepath")
                .foregroundStyle(.orange)
        case .failed:
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.red)
        }
    }

    @ViewBuilder
    private func statusLabel(for state: FileImportState) -> some View {
        switch state.phase {
        case .pending:
            Text("Waiting...")
        case .uploading:
            Text("Uploading...")
        case .processing(let status):
            Text(status.displayLabel)
        case .duplicate:
            Text("Duplicate — existing document used")
        case .failed(let message):
            Text(message)
        }
    }
}

// MARK: - State types

struct FileImportState: Identifiable {
    let id: UUID
    let filename: String
    let fileURL: URL
    var phase: ImportPhase
    var documentId: UUID?
}

enum ImportPhase {
    case pending
    case uploading
    case processing(ProcessingStatus)
    case duplicate
    case failed(String)

    var isTerminal: Bool {
        switch self {
        case .processing(let status):
            !status.isProcessing
        case .duplicate, .failed:
            true
        case .pending, .uploading:
            false
        }
    }
}
