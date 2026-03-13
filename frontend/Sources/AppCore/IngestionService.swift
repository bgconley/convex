import Domain
import Foundation

package actor IngestionService {
    private let docRepo: any DocumentRepositoryPort
    private var latestEvents: [UUID: ProcessingEvent] = [:]
    private var continuations: [UUID: [UUID: AsyncStream<ProcessingEvent>.Continuation]] = [:]

    package init(docRepo: any DocumentRepositoryPort) {
        self.docRepo = docRepo
    }

    /// Upload a file and return the upload response.
    /// If the file is a duplicate, returns the existing document ID.
    package func uploadFile(at url: URL) async throws -> DocumentUploadResponse {
        try await docRepo.upload(fileURL: url)
    }

    /// Upload multiple files concurrently.
    package func uploadFiles(at urls: [URL]) async -> [(URL, Result<DocumentUploadResponse, Error>)] {
        await withTaskGroup(of: (URL, Result<DocumentUploadResponse, Error>).self) { group in
            for url in urls {
                group.addTask {
                    do {
                        let result = try await self.docRepo.upload(fileURL: url)
                        return (url, .success(result))
                    } catch {
                        return (url, .failure(error))
                    }
                }
            }
            var results: [(URL, Result<DocumentUploadResponse, Error>)] = []
            for await result in group {
                results.append(result)
            }
            return results
        }
    }

    package func handle(event: ProcessingEvent) {
        latestEvents[event.documentId] = event
        let listeners = continuations[event.documentId] ?? [:]
        for continuation in listeners.values {
            continuation.yield(event)
        }
        if event.isTerminal {
            for continuation in listeners.values {
                continuation.finish()
            }
            continuations[event.documentId] = nil
        }
    }

    package func latestEvent(for documentId: UUID) -> ProcessingEvent? {
        latestEvents[documentId]
    }

    package func eventStream(for documentId: UUID) -> AsyncStream<ProcessingEvent> {
        AsyncStream { continuation in
            let token = UUID()
            if let event = latestEvents[documentId] {
                continuation.yield(event)
                if event.isTerminal {
                    continuation.finish()
                    return
                }
            }

            var listeners = continuations[documentId] ?? [:]
            listeners[token] = continuation
            continuations[documentId] = listeners

            continuation.onTermination = { [documentId] _ in
                Task {
                    await self.removeContinuation(token, for: documentId)
                }
            }
        }
    }

    private func removeContinuation(_ token: UUID, for documentId: UUID) {
        guard var listeners = continuations[documentId] else { return }
        listeners[token] = nil
        if listeners.isEmpty {
            continuations[documentId] = nil
        } else {
            continuations[documentId] = listeners
        }
    }
}
