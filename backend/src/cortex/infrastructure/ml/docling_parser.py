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
        try:
            if file_type == "txt":
                return self._parse_plain_text(file_path)

            # For images: convert to single-page PDF first so the GPU-configured
            # PDF pipeline (EasyOCR + layout model) handles OCR instead of
            # Docling's IMAGE pipeline which falls back to RapidOCR/ONNX on CPU.
            actual_path = file_path
            temp_pdf = None
            if file_type in ("png", "jpg", "tiff"):
                temp_pdf = self._image_to_temp_pdf(file_path)
                actual_path = temp_pdf
                file_type = "pdf"

            result = self._converter.convert(str(actual_path))
            doc = result.document

            text = doc.export_to_markdown()
            rendered_html = doc.export_to_html()
            structured = doc.export_to_dict()

            word_count = len(text.split()) if text else 0

            page_count = None
            images: list[ExtractedImage] = []

            if file_type == "pdf":
                page_count, _, images = self._extract_pdf_assets(
                    actual_path
                )

            # Clean up temp PDF if we created one
            if temp_pdf is not None:
                temp_pdf.unlink(missing_ok=True)

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
        finally:
            # Always release GPU memory after every parse, including txt
            self._clear_gpu_cache()

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
    def _image_to_temp_pdf(image_path: Path) -> Path:
        """Convert an image file to a single-page PDF so it goes through the
        GPU-configured PDF pipeline (EasyOCR) instead of the IMAGE pipeline
        (RapidOCR/ONNX on CPU)."""
        import fitz  # PyMuPDF
        import tempfile

        img_doc = fitz.open(str(image_path))
        pdf_doc = fitz.open()
        page = img_doc[0]
        rect = page.rect
        pdf_page = pdf_doc.new_page(width=rect.width, height=rect.height)
        pdf_page.insert_image(rect, filename=str(image_path))
        temp_path = Path(tempfile.mktemp(suffix=".pdf"))
        pdf_doc.save(str(temp_path))
        pdf_doc.close()
        img_doc.close()
        return temp_path

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
