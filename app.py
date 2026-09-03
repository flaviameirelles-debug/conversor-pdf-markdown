"""
Núcleo de conversão de PDF para Markdown usando PyMuPDF (fitz).

Regras principais:
- Não resume, não interpreta e não altera o conteúdo textual.
- Preserva a ordem das páginas.
- Cada página é delimitada por marcadores explícitos.
- Imagens são embutidas diretamente no Markdown em base64 (data URI) —
  não é mais gerada uma pasta "imagens" nem um .zip. O resultado é sempre
  um único arquivo .md, o que evita problemas de download de .zip
  bloqueado por antivírus/rede em alguns computadores.
- Comprime/redimensiona imagens grandes para reduzir o tamanho final do .md.
- Tenta preservar tabelas em formato Markdown.
- Usa heurística de tamanho de fonte para detectar títulos/subtítulos.
"""

import io
import base64
import statistics
import fitz  # PyMuPDF

try:
    from PIL import Image
    PIL_DISPONIVEL = True
except ImportError:
    PIL_DISPONIVEL = False

MAX_IMAGE_DIMENSION = 1600
JPEG_QUALITY = 78

_MIME_POR_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "webp": "image/webp",
}


def _mime_type(ext):
    return _MIME_POR_EXT.get(ext.lower(), "application/octet-stream")


def _heading_level(font_size, body_size):
    if body_size <= 0:
        return None
    ratio = font_size / body_size
    if ratio >= 1.8:
        return 1
    elif ratio >= 1.5:
        return 2
    elif ratio >= 1.25:
        return 3
    elif ratio >= 1.12:
        return 4
    return None


def _dominant_font_size(page_dict):
    sizes = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if text:
                    sizes.append(round(span.get("size", 0), 1))
    if not sizes:
        return 0
    try:
        return statistics.mode(sizes)
    except statistics.StatisticsError:
        return sorted(sizes)[len(sizes) // 2]


def _span_is_bold(span):
    font = span.get("font", "").lower()
    flags = span.get("flags", 0)
    return "bold" in font or bool(flags & 2 ** 4)


def _line_to_markdown(line, body_size):
    spans = line.get("spans", [])
    texts = [s.get("text", "") for s in spans]
    raw_line = "".join(texts)
    stripped = raw_line.strip()
    if not stripped:
        return ""

    max_size = max((round(s.get("size", 0), 1) for s in spans), default=body_size)
    level = _heading_level(max_size, body_size)

    parts = []
    for span in spans:
        text = span.get("text", "")
        if not text:
            continue
        if span.get("text", "").strip() == "":
            parts.append(text)
            continue
        bold = _span_is_bold(span)
        italic = bool(span.get("flags", 0) & 2 ** 1)
        formatted = text
        if bold and italic:
            formatted = f"***{text}***"
        elif bold:
            formatted = f"**{text}**"
        elif italic:
            formatted = f"*{text}*"
        parts.append(formatted)
    content = "".join(parts).strip()

    bullet_prefixes = ("•", "◦", "▪", "-", "*", "‣")
    is_bullet = False
    for prefix in bullet_prefixes:
        if stripped.startswith(prefix + " ") or stripped == prefix:
            is_bullet = True
            content = content.lstrip("".join(bullet_prefixes) + " ").strip()
            break

    if level:
        return f"{'#' * (level + 1)} {content}"
    if is_bullet:
        return f"- {content}"
    return content


def _table_to_markdown(table):
    try:
        data = table.extract()
    except Exception:
        return ""
    if not data or not any(any(cell for cell in row) for row in data):
        return ""

    rows = [[("" if cell is None else str(cell).replace("\n", " ").strip()) for cell in row] for row in data]
    n_cols = max(len(r) for r in rows)
    rows = [r + [""] * (n_cols - len(r)) for r in rows]

    lines = []
    header = rows[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * n_cols) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _comprimir_imagem(image_bytes, ext):
    if not PIL_DISPONIVEL:
        return image_bytes, ext

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception:
        return image_bytes, ext

    largura, altura = img.size
    maior_lado = max(largura, altura)
    if maior_lado > MAX_IMAGE_DIMENSION:
        escala = MAX_IMAGE_DIMENSION / float(maior_lado)
        nova_largura = max(1, int(largura * escala))
        nova_altura = max(1, int(altura * escala))
        try:
            img = img.resize((nova_largura, nova_altura), Image.LANCZOS)
        except Exception:
            pass

    tem_transparencia = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)

    buffer = io.BytesIO()
    try:
        if tem_transparencia:
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            img.save(buffer, format="PNG", optimize=True)
            nova_ext = "png"
        else:
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            nova_ext = "jpg"
    except Exception:
        return image_bytes, ext

    novos_bytes = buffer.getvalue()

    if len(novos_bytes) < len(image_bytes):
        return novos_bytes, nova_ext
    return image_bytes, ext


def _imagem_para_data_uri(image_bytes, ext):
    mime = _mime_type(ext)
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def convert_pdf(pdf_bytes, progress_callback=None, filename_prefix=""):
    """
    Converte o PDF em um único texto Markdown, com as imagens já
    embutidas em base64 (data URI) dentro do próprio texto.

    Não recebe mais output_dir/images_dirname: não há arquivos
    intermediários nem pasta de imagens — tudo fica em memória e
    dentro da string Markdown retornada.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    markdown_parts = []
    tem_imagens = False

    for page_index in range(total_pages):
        page_num = page_index + 1
        page = doc[page_index]

        if progress_callback:
            progress_callback(page_num, total_pages)

        page_dict = page.get_text("dict")
        body_size = _dominant_font_size(page_dict)

        table_bboxes = []
        table_markdowns = []
        try:
            tables = page.find_tables()
            for t in tables.tables:
                md = _table_to_markdown(t)
                if md:
                    table_bboxes.append(fitz.Rect(t.bbox))
                    table_markdowns.append((fitz.Rect(t.bbox).y0, md))
        except Exception:
            pass

        def in_table(bbox_tuple):
            r = fitz.Rect(bbox_tuple)
            for tb in table_bboxes:
                if tb.contains(r) or tb.intersects(r):
                    return True
            return False

        content_lines = []
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            if in_table(block.get("bbox")):
                continue
            block_lines = []
            for line in block.get("lines", []):
                md_line = _line_to_markdown(line, body_size)
                if md_line:
                    block_lines.append(md_line)
            if block_lines:
                content_lines.append("\n".join(block_lines))

        body_text = "\n\n".join(content_lines).strip()

        page_md_sections = []
        if body_text:
            page_md_sections.append(body_text)
        for _, table_md in sorted(table_markdowns, key=lambda x: x[0]):
            page_md_sections.append(table_md)

        image_list = page.get_images(full=True)
        image_counter = 0
        image_refs = []
        seen_xrefs = set()
        for img in image_list:
            xref = img[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            image_bytes = base_image["image"]
            ext = base_image.get("ext", "png")

            image_bytes, ext = _comprimir_imagem(image_bytes, ext)

            image_counter += 1
            nome_alt = f"{filename_prefix}pagina_{page_num:03d}_imagem_{image_counter:03d}"
            data_uri = _imagem_para_data_uri(image_bytes, ext)
            image_refs.append(f"![{nome_alt}]({data_uri})")
            tem_imagens = True

        if image_refs:
            page_md_sections.append("\n\n".join(image_refs))

        page_content = "\n\n".join(page_md_sections).strip()
        if not page_content:
            page_content = "*(página sem conteúdo extraível)*"

        page_block = (
            f"<!-- página {page_num} -->\n\n"
            f"{page_content}\n\n"
            f"<!-- fim da página {page_num} -->"
        )
        markdown_parts.append(page_block)

    doc.close()
    markdown_text = "\n\n".join(markdown_parts)
    return markdown_text, tem_imagens


def build_combined_markdown(items):
    parts = []
    for item in items:
        nome = item["nome_arquivo"]
        parts.append(
            f"<!-- ===== documento: {nome} ===== -->\n\n"
            f"{item['markdown']}\n\n"
            f"<!-- ===== fim do documento: {nome} ===== -->"
        )
    return "\n\n".join(parts)
