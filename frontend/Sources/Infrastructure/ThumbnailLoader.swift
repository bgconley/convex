import Foundation
import AppKit

package actor ThumbnailLoader {
    private let baseURL: URL
    private let session: URLSession
    private let cache = NSCache<NSString, NSImage>()

    package init(baseURL: URL) {
        self.baseURL = baseURL
        self.session = URLSession.shared
        cache.countLimit = 200
    }

    package func loadThumbnail(documentId: UUID) async -> NSImage? {
        let key = documentId.uuidString as NSString
        if let cached = cache.object(forKey: key) {
            return cached
        }

        let url = baseURL.appendingPathComponent("documents/\(documentId.uuidString)/thumbnail")
        guard let (data, response) = try? await session.data(from: url),
              let http = response as? HTTPURLResponse,
              http.statusCode == 200,
              let image = NSImage(data: data) else {
            return nil
        }

        cache.setObject(image, forKey: key)
        return image
    }

    package func clearCache() {
        cache.removeAllObjects()
    }
}
