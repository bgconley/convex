import SwiftUI
import PDFKit

struct PDFDocumentView: NSViewRepresentable {
    let data: Data
    let pageNumber: Int?

    init(data: Data, pageNumber: Int? = nil) {
        self.data = data
        self.pageNumber = pageNumber
    }

    func makeNSView(context: Context) -> PDFView {
        let pdfView = PDFView()
        pdfView.autoScales = true
        pdfView.displayMode = .singlePageContinuous
        pdfView.displayDirection = .vertical
        let document = PDFDocument(data: data)
        pdfView.document = document
        goToPage(pdfView: pdfView, document: document)
        return pdfView
    }

    func updateNSView(_ pdfView: PDFView, context: Context) {
        let dataChanged = pdfView.document?.dataRepresentation() != data
        if dataChanged {
            let document = PDFDocument(data: data)
            pdfView.document = document
        }
        // Always navigate to the requested page — handles both initial load
        // and repeated search-hit navigation within the same document
        goToPage(pdfView: pdfView, document: pdfView.document)
    }

    private func goToPage(pdfView: PDFView, document: PDFDocument?) {
        guard let pageNumber, let document else { return }
        let pageIndex = max(0, pageNumber - 1)
        if pageIndex < document.pageCount, let page = document.page(at: pageIndex) {
            pdfView.go(to: page)
        }
    }
}
