import Domain
import Foundation

package actor IngestionService {
    private let docRepo: any DocumentRepositoryPort

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
}
