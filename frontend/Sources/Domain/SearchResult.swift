import Foundation

package struct SearchRequest: Sendable, Codable {
    package let query: String
    package var topK: Int = 10
    package var filters: SearchFilters?
    package var includeGraph: Bool = true
    package var rerank: Bool = true

    enum CodingKeys: String, CodingKey {
        case query, filters, rerank
        case topK = "top_k"
        case includeGraph = "include_graph"
    }

    package init(query: String, topK: Int = 10, filters: SearchFilters? = nil) {
        self.query = query
        self.topK = topK
        self.filters = filters
    }
}

package struct SearchFilters: Sendable, Codable {
    package var fileTypes: [String]?
    package var collectionIds: [UUID]?
    package var tags: [String]?

    enum CodingKeys: String, CodingKey {
        case tags
        case fileTypes = "file_types"
        case collectionIds = "collection_ids"
    }
}

package struct SearchResponse: Sendable, Codable {
    package let query: String
    package let results: [SearchResultItem]
    package let totalCandidates: Int
    package let searchTimeMs: Double

    enum CodingKeys: String, CodingKey {
        case query, results
        case totalCandidates = "total_candidates"
        case searchTimeMs = "search_time_ms"
    }

    package init(query: String, results: [SearchResultItem], totalCandidates: Int, searchTimeMs: Double) {
        self.query = query
        self.results = results
        self.totalCandidates = totalCandidates
        self.searchTimeMs = searchTimeMs
    }
}

package struct SearchResultItem: Sendable, Codable, Identifiable {
    package let chunkId: UUID
    package let documentId: UUID
    package let documentTitle: String
    package let documentType: String
    package let chunkText: String
    package let highlightedSnippet: String
    package let sectionHeading: String?
    package let pageNumber: Int?
    package let score: Double
    package let scoreBreakdown: ScoreBreakdown
    package let chunkStartChar: Int
    package let chunkEndChar: Int
    package let anchorId: String?

    package var id: UUID { chunkId }

    enum CodingKeys: String, CodingKey {
        case score
        case chunkId = "chunk_id"
        case documentId = "document_id"
        case documentTitle = "document_title"
        case documentType = "document_type"
        case chunkText = "chunk_text"
        case highlightedSnippet = "highlighted_snippet"
        case sectionHeading = "section_heading"
        case pageNumber = "page_number"
        case scoreBreakdown = "score_breakdown"
        case chunkStartChar = "chunk_start_char"
        case chunkEndChar = "chunk_end_char"
        case anchorId = "anchor_id"
    }
}

package struct ScoreBreakdown: Sendable, Codable, Equatable {
    package let vectorScore: Double?
    package let bm25Score: Double?
    package let graphScore: Double?
    package let rerankScore: Double?

    enum CodingKeys: String, CodingKey {
        case vectorScore = "vector_score"
        case bm25Score = "bm25_score"
        case graphScore = "graph_score"
        case rerankScore = "rerank_score"
    }
}
