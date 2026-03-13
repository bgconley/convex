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
    package var entityTypes: [String]?
    package var dateFrom: Date?
    package var dateTo: Date?

    package init(
        fileTypes: [String]? = nil,
        collectionIds: [UUID]? = nil,
        tags: [String]? = nil,
        entityTypes: [String]? = nil,
        dateFrom: Date? = nil,
        dateTo: Date? = nil
    ) {
        self.fileTypes = fileTypes
        self.collectionIds = collectionIds
        self.tags = tags
        self.entityTypes = entityTypes
        self.dateFrom = dateFrom
        self.dateTo = dateTo
    }

    enum CodingKeys: String, CodingKey {
        case tags
        case fileTypes = "file_types"
        case collectionIds = "collection_ids"
        case entityTypes = "entity_types"
        case dateFrom = "date_from"
        case dateTo = "date_to"
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

package struct EntityMention: Sendable, Codable {
    package let name: String
    package let entityType: String
    package let confidence: Double

    enum CodingKeys: String, CodingKey {
        case name, confidence
        case entityType = "entity_type"
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
    package let entities: [EntityMention]
    package let chunkStartChar: Int
    package let chunkEndChar: Int
    package let anchorId: String?

    package var id: UUID { chunkId }

    enum CodingKeys: String, CodingKey {
        case score, entities
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

package struct DocumentSearchResponse: Sendable, Codable {
    package let query: String
    package let results: [DocumentSearchResultItem]
    package let totalDocuments: Int
    package let searchTimeMs: Double

    package init(query: String, results: [DocumentSearchResultItem], totalDocuments: Int, searchTimeMs: Double) {
        self.query = query
        self.results = results
        self.totalDocuments = totalDocuments
        self.searchTimeMs = searchTimeMs
    }

    enum CodingKeys: String, CodingKey {
        case query, results
        case totalDocuments = "total_documents"
        case searchTimeMs = "search_time_ms"
    }
}

package struct SuggestionItem: Sendable, Codable, Identifiable, Equatable {
    package let value: String
    package let label: String
    package let type: String
    package let resourceId: UUID?
    package let entityType: String?

    package var id: String {
        if let resourceId {
            return resourceId.uuidString
        }
        return "\(type)|\(entityType ?? "")|\(value)"
    }

    package enum CodingKeys: String, CodingKey {
        case value, label, type
        case resourceId = "id"
        case entityType = "entity_type"
    }
}

package struct SearchSuggestionsResponse: Sendable, Codable {
    package let query: String
    package let recentSearches: [SuggestionItem]
    package let entities: [SuggestionItem]
    package let documents: [SuggestionItem]

    package init(
        query: String,
        recentSearches: [SuggestionItem],
        entities: [SuggestionItem],
        documents: [SuggestionItem]
    ) {
        self.query = query
        self.recentSearches = recentSearches
        self.entities = entities
        self.documents = documents
    }

    enum CodingKeys: String, CodingKey {
        case query, entities, documents
        case recentSearches = "recent_searches"
    }
}

package struct DocumentSearchResultItem: Sendable, Codable, Identifiable {
    package let documentId: UUID
    package let documentTitle: String
    package let documentType: String
    package let score: Double
    package let scoreBreakdown: ScoreBreakdown
    package let bestChunkSnippet: String
    package let bestChunkSection: String?
    package let bestChunkPage: Int?
    package let bestChunkAnchorId: String?
    package let chunkCount: Int

    package var id: UUID { documentId }

    enum CodingKeys: String, CodingKey {
        case score
        case documentId = "document_id"
        case documentTitle = "document_title"
        case documentType = "document_type"
        case scoreBreakdown = "score_breakdown"
        case bestChunkSnippet = "best_chunk_snippet"
        case bestChunkSection = "best_chunk_section"
        case bestChunkPage = "best_chunk_page"
        case bestChunkAnchorId = "best_chunk_anchor_id"
        case chunkCount = "chunk_count"
    }
}
