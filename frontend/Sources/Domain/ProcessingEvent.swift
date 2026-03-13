import Foundation

package struct ProcessingEvent: Sendable, Codable {
    package let eventType: String
    package let documentId: UUID
    package let status: String
    package let progressPct: Double?
    package let stageLabel: String?
    package let errorMessage: String?

    package var processingStatus: ProcessingStatus? {
        ProcessingStatus(rawValue: status)
    }

    package var isTerminal: Bool {
        guard let processingStatus else {
            return status == ProcessingStatus.ready.rawValue || status == ProcessingStatus.failed.rawValue
        }
        return !processingStatus.isProcessing
    }

    enum CodingKeys: String, CodingKey {
        case status
        case eventType = "event_type"
        case documentId = "document_id"
        case progressPct = "progress_pct"
        case stageLabel = "stage_label"
        case errorMessage = "error_message"
    }
}
