from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from cortex.domain.document import DocumentMetadata, ExtractedImage, ParseResult

logger = logging.getLogger(__name__)

# File type → Docling InputFormat mapping
_FORMAT_MAP: dict[str, str] = {
    "pdf": "PDF",
    "docx": "DOCX",
    "xlsx": "XLSX",
    "markdown": "MD",
    "txt": "MD",  # Docling treats plain text similarly
    "png": "IMAGE",
    "jpg": "IMAGE",
    "tiff": "IMAGE",
}


class DoclingParser:
    """ParserPort implementation using IBM Docling with GPU acceleration.

    GPU acceleration details (benchmarked on NVIDIA L4):
    - Layout model (RT-DETR): 14.4x speedup (44ms vs 633ms/page)
    - TableFormer: 4.3x speedup (400ms vs 1.74s/table)
    - OCR (EasyOCR): 8.1x speedup (1.6s vs 13s/page)
    - Overall: ~6.5x speedup (0.48s vs 3.1s/page)
    - VRAM: ~1-2 GB for model weights

    Caveats:
    - TableFormer does not support GPU batching yet
    - Call torch.cuda.empty_cache() between documents to prevent VRAM leaks
    - Use EasyOCR, not RapidOCR ONNX default, for GPU acceleration
    """

    def __init__(self) -> None:
        self._converter = self._create_converter()

    @staticmethod
    def _create_converter():
        from docling.datamodel.accelerator_options import (
            AcceleratorDevice,
            AcceleratorOptions,
        )
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            EasyOcrOptions,
            PdfPipelineOptions,
            TableFormerMode,
            TableStructureOptions,
        )
        from docling.document_converter import (
            DocumentConverter,
            ExcelFormatOption,
            HTMLFormatOption,
            MarkdownFormatOption,
            PdfFormatOption,
            PowerpointFormatOption,
            WordFormatOption,
        )

        pdf_options = PdfPipelineOptions()
        pdf_options.do_ocr = True
        pdf_options.do_table_structure = True
        pdf_options.table_structure_options = TableStructureOptions(
            do_cell_matching=True,
            mode=TableFormerMode.ACCURATE,
        )
        pdf_options.accelerator_options = AcceleratorOptions(
            device=AcceleratorDevice.AUTO,
        )
        # EasyOCR with GPU — RapidOCR's ONNX default ignores CUDA
        pdf_options.ocr_options = EasyOcrOptions(
            lang=["en"],
            use_gpu=True,
            confidence_threshold=0.5,
        )
        # GPU batch sizes — tuned for RTX 3090 (24 GB VRAM)
        pdf_options.ocr_batch_size = 32
        pdf_options.layout_batch_size = 32
        pdf_options.table_batch_size = 4  # GPU batching not yet supported

        return DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.DOCX,
                InputFormat.PPTX,
                InputFormat.XLSX,
                InputFormat.HTML,
                InputFormat.MD,
                InputFormat.IMAGE,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                InputFormat.DOCX: WordFormatOption(),
                InputFormat.PPTX: PowerpointFormatOption(),
                InputFormat.XLSX: ExcelFormatOption(),
                InputFormat.HTML: HTMLFormatOption(),
                InputFormat.MD: MarkdownFormatOption(),
            },
        )

    async def parse(self, file_path: Path, file_type: str) -> ParseResult:
        if file_type == "txt":
            return self._parse_plain_text(file_path)

        result = self._converter.convert(str(file_path))
        doc = result.document

        text = doc.export_to_markdown()
        rendered_html = doc.export_to_html()
        structured = doc.export_to_dict()

        # Count words from the markdown text
        word_count = len(text.split()) if text else 0

        # Extract page count for PDFs via PyMuPDF (faster than Docling for this)
        page_count = None
        thumbnail_data = None
        images: list[ExtractedImage] = []

        if file_type == "pdf":
            page_count, thumbnail_data, images = self._extract_pdf_assets(file_path)
        elif file_type in ("png", "jpg", "tiff"):
            thumbnail_data = file_path.read_bytes()

        # Release GPU memory between documents
        self._clear_gpu_cache()

        return ParseResult(
            text=text,
            structured=structured,
            rendered_html=rendered_html,
            rendered_markdown=text,
            metadata=DocumentMetadata(
                page_count=page_count,
                word_count=word_count,
            ),
            images=images,
            page_count=page_count,
        )

    @staticmethod
    def _parse_plain_text(file_path: Path) -> ParseResult:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        import html as html_module

        escaped = html_module.escape(content)
        rendered_html = f"<pre>{escaped}</pre>"
        word_count = len(content.split())

        return ParseResult(
            text=content,
            structured={"type": "plain_text", "content": content},
            rendered_html=rendered_html,
            rendered_markdown=content,
            metadata=DocumentMetadata(word_count=word_count),
        )

    @staticmethod
    def _extract_pdf_assets(
        file_path: Path,
    ) -> tuple[int, bytes | None, list[ExtractedImage]]:
        """Extract page count, thumbnail, and images from PDF via PyMuPDF."""
        import fitz  # PyMuPDF

        pdf_doc = fitz.open(str(file_path))
        page_count = len(pdf_doc)

        # Generate thumbnail from first page
        thumbnail_data = None
        if page_count > 0:
            page = pdf_doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
            thumbnail_data = pix.tobytes("png")

        # Extract embedded images
        images: list[ExtractedImage] = []
        for page_idx in range(page_count):
            page = pdf_doc[page_idx]
            for img_idx, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = pdf_doc.extract_image(xref)
                if base_image:
                    images.append(
                        ExtractedImage(
                            image_path="",  # set by caller when saving
                            page_number=page_idx + 1,
                            width=base_image.get("width"),
                            height=base_image.get("height"),
                        )
                    )

        pdf_doc.close()
        return page_count, thumbnail_data, images

    @staticmethod
    def _clear_gpu_cache() -> None:
        """Release VRAM between documents to prevent leaks (known Docling issue)."""
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
