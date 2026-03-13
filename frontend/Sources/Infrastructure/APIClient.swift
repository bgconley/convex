import Foundation

package actor APIClient: Sendable {
    private let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder

    package init(baseURL: URL) {
        self.baseURL = baseURL
        self.session = URLSession.shared
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let string = try container.decode(String.self)

            // Try ISO 8601 with fractional seconds first, then without
            let formatters: [ISO8601DateFormatter] = {
                let withFrac = ISO8601DateFormatter()
                withFrac.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                let without = ISO8601DateFormatter()
                without.formatOptions = [.withInternetDateTime]
                return [withFrac, without]
            }()

            for formatter in formatters {
                if let date = formatter.date(from: string) {
                    return date
                }
            }
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Cannot decode date: \(string)")
        }
        self.decoder = decoder
    }

    package func get<T: Decodable>(_ path: String) async throws -> T {
        let url = buildURL(path)
        let (data, response) = try await session.data(from: url)
        try validateResponse(response)
        return try decoder.decode(T.self, from: data)
    }

    package func post<T: Decodable>(_ path: String, body: some Encodable) async throws -> T {
        let url = buildURL(path)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        try validateResponse(response)
        return try decoder.decode(T.self, from: data)
    }

    package func uploadMultipart<T: Decodable>(_ path: String, fileURL: URL) async throws -> T {
        let url = buildURL(path)
        let boundary = UUID().uuidString

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let fileData = try Data(contentsOf: fileURL)
        let fileName = fileURL.lastPathComponent

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: application/octet-stream\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        let (data, response) = try await session.data(for: request)
        try validateResponse(response)
        return try decoder.decode(T.self, from: data)
    }

    package func getData(_ path: String) async throws -> Data {
        let url = buildURL(path)
        let (data, response) = try await session.data(from: url)
        try validateResponse(response)
        return data
    }

    package func url(for path: String) -> URL {
        buildURL(path)
    }

    package func delete(_ path: String) async throws {
        let url = buildURL(path)
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        let (_, response) = try await session.data(for: request)
        try validateResponse(response)
    }

    package func patch<T: Decodable>(_ path: String, body: some Encodable) async throws -> T {
        let url = buildURL(path)
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        try validateResponse(response)
        return try decoder.decode(T.self, from: data)
    }

    /// Builds a URL from the base URL and a path that may contain query parameters.
    /// `appendingPathComponent` percent-encodes `?` and `=`, so we use string
    /// concatenation and `URL(string:)` instead.
    private func buildURL(_ path: String) -> URL {
        let base = baseURL.absoluteString.hasSuffix("/")
            ? baseURL.absoluteString
            : baseURL.absoluteString + "/"
        return URL(string: base + path) ?? baseURL.appendingPathComponent(path)
    }

    private func validateResponse(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(http.statusCode) else {
            throw APIError.httpError(statusCode: http.statusCode)
        }
    }
}

extension CharacterSet {
    /// Characters safe inside a URL query parameter value.
    /// `.urlQueryAllowed` still permits `&`, `=`, `+`, and `#` which are
    /// delimiters in a query string and must be percent-encoded in values.
    static let urlQueryValueAllowed: CharacterSet = {
        var cs = CharacterSet.urlQueryAllowed
        cs.remove(charactersIn: "&=+#")
        return cs
    }()
}

package enum APIError: Error, LocalizedError {
    case invalidResponse
    case httpError(statusCode: Int)

    package var errorDescription: String? {
        switch self {
        case .invalidResponse:
            "Invalid response from server"
        case .httpError(let code):
            "Server returned status \(code)"
        }
    }
}
