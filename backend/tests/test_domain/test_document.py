"""Verify domain entities are self-contained and infrastructure-free."""

from cortex.domain.document import Document, FileType, ProcessingStatus


def test_document_creation():
    doc = Document.new(
        title="Test Document",
        original_filename="test.pdf",
        file_type=FileType.PDF,
        file_size_bytes=1024,
        file_hash="abc123",
        mime_type="application/pdf",
        original_path="/data/originals/test.pdf",
    )
    assert doc.title == "Test Document"
    assert doc.file_type == FileType.PDF
    assert doc.status == ProcessingStatus.UPLOADING
    assert doc.id is not None


def test_processing_status_values():
    """Status values match the canonical lifecycle in APP_SPEC."""
    expected = [
        "uploading", "stored", "parsing", "parsed",
        "chunking", "chunked", "embedding", "embedded",
        "extracting_entities", "entities_extracted",
        "building_graph", "ready", "failed",
    ]
    actual = [s.value for s in ProcessingStatus]
    assert actual == expected
