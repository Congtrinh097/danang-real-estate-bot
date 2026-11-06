import io
import os
from typing import Optional
from pypdf import PdfReader
from docx import Document

class DocumentConverter:
    """Chuyển đổi các định dạng tài liệu (PDF, Word DOCX, Markdown, Text) sang định dạng Markdown chuẩn hóa."""

    @staticmethod
    def convert_to_markdown(file_bytes: bytes, filename: str) -> str:
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError("File tải lên rỗng (0 bytes). Vui lòng chọn file có nội dung.")

        ext = os.path.splitext(filename)[1].lower()
        
        if ext in [".md", ".markdown", ".txt"]:
            return DocumentConverter._convert_text_or_markdown(file_bytes)
        elif ext in [".docx"]:
            return DocumentConverter._convert_docx(file_bytes)
        elif ext in [".pdf"]:
            return DocumentConverter._convert_pdf(file_bytes)
        else:
            raise ValueError(f"Định dạng file không được hỗ trợ ({ext}). Chỉ hỗ trợ .pdf, .docx, .md, .txt")

    @staticmethod
    def _convert_text_or_markdown(file_bytes: bytes) -> str:
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="ignore")

    @staticmethod
    def _convert_docx(file_bytes: bytes) -> str:
        doc = Document(io.BytesIO(file_bytes))
        md_lines = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            style_name = p.style.name.lower() if p.style else ""
            if "heading 1" in style_name:
                md_lines.append(f"# {text}\n")
            elif "heading 2" in style_name:
                md_lines.append(f"## {text}\n")
            elif "heading 3" in style_name:
                md_lines.append(f"### {text}\n")
            else:
                md_lines.append(f"{text}\n")

        for table in doc.tables:
            table_md = []
            for row in table.rows:
                row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                table_md.append("| " + " | ".join(row_cells) + " |")
            if table_md:
                # Thêm header separator sau hàng đầu tiên
                header_sep = "| " + " | ".join(["---"] * len(table.rows[0].cells)) + " |"
                table_md.insert(1, header_sep)
                md_lines.append("\n" + "\n".join(table_md) + "\n")

        return "\n".join(md_lines)

    @staticmethod
    def _extract_with_pypdf(file_bytes: bytes) -> str:
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for page in reader.pages:
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        pages_text.append(text.strip())
                except Exception:
                    continue
            return "\n\n".join(pages_text).strip()
        except Exception:
            return ""

    @staticmethod
    def _extract_with_pypdfium2(file_bytes: bytes) -> str:
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(file_bytes)
            pages_text = []
            for page in pdf:
                try:
                    tp = page.get_textpage()
                    text = tp.get_text_range()
                    if text and text.strip():
                        pages_text.append(text.strip())
                except Exception:
                    continue
            return "\n\n".join(pages_text).strip()
        except Exception:
            return ""

    @staticmethod
    def _convert_pdf(file_bytes: bytes, filename: str = "document.pdf") -> str:
        # Bước 1: Trích xuất nhanh bằng pypdf
        raw_text = DocumentConverter._extract_with_pypdf(file_bytes)

        # Bước 2: Nếu pypdf không lấy được text (font mã hóa đặc thù), dùng pypdfium2 (PDFium engine)
        if not raw_text or len(raw_text.strip()) < 10:
            pdfium_text = DocumentConverter._extract_with_pypdfium2(file_bytes)
            if pdfium_text and len(pdfium_text.strip()) >= 10:
                raw_text = pdfium_text

        # Nếu trích xuất được text rõ ràng từ text layer, chuẩn hóa sang Markdown
        if raw_text and len(raw_text.strip()) >= 10:
            return DocumentConverter._format_markdown_legal(raw_text)

        # Bước 3: Nếu PDF hoàn toàn không có text layer (file PDF scan / dạng ảnh), kích hoạt Docling OCR
        ocr_result = DocumentConverter.convert_with_docling(file_bytes, filename)
        if ocr_result and ocr_result.strip():
            return DocumentConverter._format_markdown_legal(ocr_result.strip())

        raise ValueError("Không trích xuất được nội dung văn bản từ file PDF (file scan dạng ảnh hoặc trang trắng không nhận diện được chữ). Vui lòng cung cấp file PDF chứa text hoặc định dạng Word/Markdown.")

    @staticmethod
    def _format_markdown_legal(raw_text: str) -> str:
        lines = raw_text.split("\n")
        formatted_lines = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            lower_str = line_str.lower()
            if lower_str.startswith("chương ") or lower_str.startswith("mục "):
                formatted_lines.append(f"\n## {line_str}\n")
            elif lower_str.startswith("điều ") or lower_str.startswith("dieu "):
                formatted_lines.append(f"\n### {line_str}\n")
            else:
                formatted_lines.append(line_str)
        return "\n".join(formatted_lines)

    @staticmethod
    def convert_with_docling(file_bytes: bytes, filename: str = "document.pdf") -> Optional[str]:
        """Sử dụng Docling với OCR (RapidOCR) để trích xuất cấu trúc văn bản Markdown từ tài liệu scan hoặc phức tạp."""
        try:
            from docling.document_converter import DocumentConverter as DoclingConverter, PdfFormatOption
            from docling.datamodel.base_models import DocumentStream
            from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
            from docling.datamodel.document import ConversionStatus

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True
            pipeline_options.ocr_options = RapidOcrOptions()
            pipeline_options.do_table_structure = False  # Bỏ qua TableFormer để tăng tốc độ xử lý trên CPU
            pipeline_options.generate_page_images = False
            pipeline_options.generate_picture_images = False
            pipeline_options.generate_table_images = False
            pipeline_options.images_scale = 1.0
            pipeline_options.document_timeout = 60.0  # Giới hạn timeout 60s tránh treo tiến trình

            doc_converter = DoclingConverter(
                format_options={
                    "pdf": PdfFormatOption(pipeline_options=pipeline_options)
                }
            )

            stream = DocumentStream(name=filename, stream=io.BytesIO(file_bytes))
            conv_res = doc_converter.convert(stream)

            # Kiểm tra lỗi timeout từ Docling
            if conv_res:
                is_timeout = False
                if hasattr(conv_res, "has_timeout_errors") and conv_res.has_timeout_errors():
                    is_timeout = True
                elif getattr(conv_res, "errors", None):
                    for err in conv_res.errors:
                        err_cat = str(getattr(err, "category", "")).lower()
                        err_msg = str(getattr(err, "error_message", "")).lower()
                        if "timeout" in err_cat or "timeout" in err_msg:
                            is_timeout = True
                            break

                if is_timeout:
                    raise TimeoutError(
                        f"Quá thời gian xử lý file PDF ({pipeline_options.document_timeout:.0f}s). "
                        "Tài liệu scan quá dài hoặc chứa quá nhiều trang để nhận diện OCR kịp thời. "
                        "Vui lòng cung cấp file PDF chứa text layer gốc hoặc định dạng Word/Markdown."
                    )

                if getattr(conv_res, "status", None) == ConversionStatus.FAILURE:
                    raise ValueError("Docling OCR chuyển đổi thất bại. Không thể nhận diện nội dung từ tài liệu.")

                if conv_res.document:
                    return conv_res.document.export_to_markdown()
        except (TimeoutError, ValueError):
            raise
        except Exception as e:
            err_msg = str(e).lower()
            if "timeout" in err_msg or "time budget exhausted" in err_msg:
                raise TimeoutError(
                    f"Quá thời gian xử lý file PDF (60s). "
                    "Tài liệu scan quá dài để nhận diện OCR kịp thời. "
                    "Vui lòng cung cấp file PDF chứa text layer gốc hoặc định dạng Word/Markdown."
                )
            print(f"[WARN] Docling OCR chuyển đổi thất bại hoặc gặp lỗi: {e}")
        return None
