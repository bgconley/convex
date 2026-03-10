import SwiftUI
import AppKit

struct ImageDocumentView: View {
    let imageData: Data

    @State private var scale: CGFloat = 1.0
    @State private var lastScale: CGFloat = 1.0
    @State private var offset: CGSize = .zero
    @State private var lastOffset: CGSize = .zero

    var body: some View {
        GeometryReader { geometry in
            if let nsImage = NSImage(data: imageData) {
                Image(nsImage: nsImage)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .scaleEffect(scale)
                    .offset(offset)
                    .gesture(magnificationGesture)
                    .gesture(dragGesture)
                    .frame(width: geometry.size.width, height: geometry.size.height)
                    .clipped()
            } else {
                ContentUnavailableView("Unable to load image", systemImage: "photo.badge.exclamationmark")
            }
        }
        .toolbar {
            ToolbarItemGroup(placement: .automatic) {
                Button {
                    withAnimation { scale = max(0.1, scale - 0.25) }
                } label: {
                    Image(systemName: "minus.magnifyingglass")
                }
                .help("Zoom out")

                Button {
                    withAnimation {
                        scale = 1.0
                        offset = .zero
                    }
                } label: {
                    Text("\(Int(scale * 100))%")
                        .monospacedDigit()
                        .frame(width: 50)
                }
                .help("Reset zoom")

                Button {
                    withAnimation { scale += 0.25 }
                } label: {
                    Image(systemName: "plus.magnifyingglass")
                }
                .help("Zoom in")
            }
        }
    }

    private var magnificationGesture: some Gesture {
        MagnifyGesture()
            .onChanged { value in
                scale = lastScale * value.magnification
            }
            .onEnded { _ in
                lastScale = scale
            }
    }

    private var dragGesture: some Gesture {
        DragGesture()
            .onChanged { value in
                offset = CGSize(
                    width: lastOffset.width + value.translation.width,
                    height: lastOffset.height + value.translation.height
                )
            }
            .onEnded { _ in
                lastOffset = offset
            }
    }
}
