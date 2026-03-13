import Foundation
import Domain

/// Connects to the backend WebSocket endpoint for real-time processing events.
/// Reconnects automatically on disconnect.
package actor WebSocketClient {
    private let url: URL
    private var task: URLSessionWebSocketTask?
    private let session = URLSession.shared
    private var onEvent: (@Sendable (ProcessingEvent) -> Void)?
    private var isConnected = false
    private var shouldReconnect = false

    package init(baseURL: URL) {
        var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false)!
        components.scheme = components.scheme == "https" ? "wss" : "ws"
        components.path = "/api/v1/ws/events"
        self.url = components.url!
    }

    package func connect(onEvent: @Sendable @escaping (ProcessingEvent) -> Void) {
        self.onEvent = onEvent
        shouldReconnect = true
        reconnect()
    }

    package func disconnect() {
        shouldReconnect = false
        isConnected = false
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
    }

    private func reconnect() {
        guard shouldReconnect, !isConnected else { return }
        let wsTask = session.webSocketTask(with: url)
        self.task = wsTask
        wsTask.resume()
        isConnected = true
        receiveLoop(wsTask)
    }

    private func receiveLoop(_ wsTask: URLSessionWebSocketTask) {
        wsTask.receive { [weak self] result in
            Task { [weak self] in
                await self?.handleReceive(result, wsTask: wsTask)
            }
        }
    }

    private func handleReceive(_ result: Result<URLSessionWebSocketTask.Message, Error>, wsTask: URLSessionWebSocketTask) {
        switch result {
        case .success(let message):
            switch message {
            case .string(let text):
                if let data = text.data(using: .utf8),
                   let event = try? JSONDecoder().decode(ProcessingEvent.self, from: data) {
                    onEvent?(event)
                }
            case .data(let data):
                if let event = try? JSONDecoder().decode(ProcessingEvent.self, from: data) {
                    onEvent?(event)
                }
            @unknown default:
                break
            }
            receiveLoop(wsTask)
        case .failure:
            isConnected = false
            guard shouldReconnect else { return }
            // Reconnect after delay
            Task {
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                reconnect()
            }
        }
    }
}
