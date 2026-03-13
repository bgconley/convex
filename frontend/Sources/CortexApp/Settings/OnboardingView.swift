import SwiftUI

struct OnboardingView: View {
    let onComplete: (URL) -> Void
    let onSkip: () -> Void

    @State private var urlString = "http://10.25.0.50:8090/api/v1"
    @State private var connectionStatus: ConnectionStatus = .idle
    @State private var errorMessage: String?

    enum ConnectionStatus {
        case idle, checking, connected, failed
    }

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "brain.head.profile")
                .font(.system(size: 56))
                .foregroundStyle(.tint)

            Text("Welcome to Cortex")
                .font(.title)
                .fontWeight(.semibold)

            Text("Your personal knowledge base. Connect to your backend server to get started.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 360)

            VStack(alignment: .leading, spacing: 8) {
                Text("Backend URL")
                    .font(.headline)

                TextField("http://10.25.0.50:8090/api/v1", text: $urlString)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 360)

                statusLabel
            }

            HStack(spacing: 12) {
                Button("Use Default") {
                    onSkip()
                }
                .buttonStyle(.bordered)

                Button("Test Connection") {
                    Task { await testConnection() }
                }
                .buttonStyle(.bordered)
                .disabled(connectionStatus == .checking || !isURLValid)

                Button("Connect") {
                    guard let url = URL(string: urlString) else { return }
                    onComplete(url)
                }
                .buttonStyle(.borderedProminent)
                .disabled(!isURLValid)
            }
        }
        .padding(40)
        .frame(width: 480, height: 400)
    }

    @ViewBuilder
    private var statusLabel: some View {
        switch connectionStatus {
        case .idle:
            EmptyView()
        case .checking:
            HStack(spacing: 6) {
                ProgressView()
                    .controlSize(.small)
                Text("Testing connection...")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        case .connected:
            Label("Connected successfully", systemImage: "checkmark.circle.fill")
                .font(.caption)
                .foregroundStyle(.green)
        case .failed:
            Label(errorMessage ?? "Connection failed", systemImage: "xmark.circle.fill")
                .font(.caption)
                .foregroundStyle(.red)
        }
    }

    private var isURLValid: Bool {
        URL(string: urlString) != nil && !urlString.isEmpty
    }

    private func testConnection() async {
        guard let url = URL(string: urlString) else { return }
        connectionStatus = .checking
        errorMessage = nil

        let healthURL = url.absoluteString.hasSuffix("/")
            ? URL(string: url.absoluteString + "health")!
            : URL(string: url.absoluteString + "/health")!

        do {
            let (_, response) = try await URLSession.shared.data(from: healthURL)
            if let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) {
                connectionStatus = .connected
            } else {
                connectionStatus = .failed
                errorMessage = "Server returned unexpected status"
            }
        } catch {
            connectionStatus = .failed
            errorMessage = error.localizedDescription
        }
    }
}
