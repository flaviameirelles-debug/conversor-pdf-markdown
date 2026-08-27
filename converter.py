"""
Núcleo de conversão de PDF para Markdown usando PyMuPDF (fitz).

Regras principais:
- Não resume, não interpreta e não altera o conteúdo textual.
- Preserva a ordem das páginas.
- Cada página é delimitada por marcadores explícitos.
- Extrai imagens para uma pasta separada e referencia via Markdown.
- Tenta preservar tabelas em formato Markdown.
- Usa heurística de tamanho de fonte para detectar títulos/subtítulos.
"""

import os
import io
import statistics
import zipfile
import fitz  # PyMuPDF


def _heading_level(font_size, body_size):
    """Define o nível de heading (## a ######) com base no tamanho da fonte
    em relação ao tamanho de fonte predominante (corpo do texto)."""
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
    """Calcula o tamanho de fonte mais comum na página (aproximação do
    'corpo do texto') para servir de referência às heurísticas de título."""
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
    """Converte uma linha de texto (spans) do PyMuPDF em texto Markdown,
    aplicando negrito/itálico span a span e detectando heading pelo maior
    tamanho de fonte da linha."""
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
        if span.get("text", "").strip() == "" :
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

    # Detecta itens de lista simples (marcadores comuns extraídos do PDF)
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
    """Converte uma tabela extraída pelo PyMuPDF (find_tables) em Markdown."""
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


def convert_pdf(pdf_bytes, output_dir, images_dirname="imagens", progress_callback=None):
    """
    Converte um PDF (bytes) em Markdown, salvando imagens extraídas em
    output_dir/images_dirname.

    Retorna o texto Markdown completo (str).
    """
    images_dir = os.path.join(output_dir, images_dirname)
    os.makedirs(images_dir, exist_ok=True)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    markdown_parts = []

    for page_index in range(total_pages):
        page_num = page_index + 1
        page = doc[page_index]

        if progress_callback:
            progress_callback(page_num, total_pages)

        page_dict = page.get_text("dict")
        body_size = _dominant_font_size(page_dict)

        # Áreas ocupadas por tabelas, para não duplicar texto das células
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

        # Insere blocos de tabela na posição vertical aproximada correta
        combined = [(0, "\n\n".join(content_lines))] if content_lines else []
        # Estratégia simples: texto primeiro, tabelas ao final do texto
        # (posição exata é difícil de garantir; mantemos ordem estável)
        body_text = "\n\n".join(content_lines).strip()

        page_md_sections = []
        if body_text:
            page_md_sections.append(body_text)
        for _, table_md in sorted(table_markdowns, key=lambda x: x[0]):
            page_md_sections.append(table_md)

        # Extração de imagens da página
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
            image_counter += 1
            ext = base_image.get("ext", "png")
            filename = f"pagina_{page_num:03d}_imagem_{image_counter:03d}.{ext}"
            filepath = os.path.join(images_dir, filename)
            with open(filepath, "wb") as f:
                f.write(base_image["image"])
            image_refs.append(f"![{filename}]({images_dirname}/{filename})")

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
    return "\n\n".join(markdown_parts)


def build_result_zip(markdown_text, output_dir, images_dirname="imagens", md_filename="documento.md"):
    """Empacota o documento.md e a pasta de imagens em um único .zip.
    Retorna o caminho do arquivo .zip gerado."""
    md_path = os.path.join(output_dir, md_filename)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    zip_path = os.path.join(output_dir, "resultado.zip")
    images_dir = os.path.join(output_dir, images_dirname)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(md_path, arcname=md_filename)
        if os.path.isdir(images_dir):
            for fname in sorted(os.listdir(images_dir)):
                fpath = os.path.join(images_dir, fname)
                if os.path.isfile(fpath):
                    zf.write(fpath, arcname=os.path.join(images_dirname, fname))

    return zip_path
