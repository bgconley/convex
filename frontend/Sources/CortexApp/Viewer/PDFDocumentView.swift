import SwiftUI
import PDFKit

struct PDFDocumentView: NSViewRepresentable {
    let data: Data
    let pageNumber: Int?
    let searchQuery: String

    init(data: Data, pageNumber: Int? = nil, searchQuery: String = "") {
        self.data = data
        self.pageNumber = pageNumber
        self.searchQuery = searchQuery
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
        findQuery(pdfView: pdfView, document: pdfView.document)
    }

    private func goToPage(pdfView: PDFView, document: PDFDocument?) {
        guard let pageNumber, let document else { return }
        let pageIndex = max(0, pageNumber - 1)
        if pageIndex < document.pageCount, let page = document.page(at: pageIndex) {
            pdfView.go(to: page)
        }
    }

    private func findQuery(pdfView: PDFView, document: PDFDocument?) {
        let trimmedQuery = searchQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedQuery.isEmpty, let document else {
            pdfView.setCurrentSelection(nil, animate: false)
            return
        }
        let matches = document.findString(trimmedQuery, withOptions: [.caseInsensitive, .diacriticInsensitive])
        guard let selection = matches.first else {
            pdfView.setCurrentSelection(nil, animate: false)
            return
        }
        pdfView.setCurrentSelection(selection, animate: true)
        pdfView.go(to: selection)
    }
}
