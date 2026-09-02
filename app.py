import os
import re
import tempfile
import streamlit as st
from converter import convert_pdf, build_result_zip

st.set_page_config(page_title="Conversor de PDF para Markdown", page_icon="📄", layout="centered")
st.title("Conversor de PDF para Markdown")
st.write("Envie um PDF, converta e baixe o resultado em Markdown (com as imagens do documento).")

if "resultado_dados" not in st.session_state:
    st.session_state.resultado_dados = None
if "resultado_nome" not in st.session_state:
    st.session_state.resultado_nome = None
if "resultado_mime" not in st.session_state:
    st.session_state.resultado_mime = None


def sanitizar_nome_arquivo(nome):
    """Remove acentos, espaços e caracteres especiais do nome do arquivo,
    para evitar problemas no header Content-Disposition do download."""
    # Remove acentos (normaliza para forma decomposta e descarta os
    # caracteres de acentuação)
    import unicodedata
    nome_sem_acento = unicodedata.normalize("NFKD", nome)
    nome_sem_acento = "".join(c for c in nome_sem_acento if not unicodedata.combining(c))

    # Substitui qualquer coisa que não seja letra/número/hífen/underscore por "_"
    nome_limpo = re.sub(r"[^a-zA-Z0-9_-]+", "_", nome_sem_acento)

    # Remove underscores duplicados e nas pontas
    nome_limpo = re.sub(r"_+", "_", nome_limpo).strip("_")

    # Garante que não fique vazio
    if not nome_limpo:
        nome_limpo = "documento"

    return nome_limpo


uploaded_file = st.file_uploader(
    "Arraste o PDF aqui ou clique em Selecionar PDF",
    type=["pdf"],
    accept_multiple_files=False,
)

if uploaded_file is not None:
    st.write(f"**Arquivo selecionado:** {uploaded_file.name}")

converter_clicado = st.button("Converter para Markdown", type="primary", disabled=uploaded_file is None)

if converter_clicado and uploaded_file is not None:
    with st.spinner("Convertendo PDF, por favor aguarde..."):
        pdf_bytes = uploaded_file.read()
        with tempfile.TemporaryDirectory() as tmp_dir:
            def progress_cb(pagina, total):
                pass  # reservado para barra de progresso futura, se necessário

            markdown_text = convert_pdf(pdf_bytes, tmp_dir, progress_callback=progress_cb)
            imagens_dir = os.path.join(tmp_dir, "imagens")
            tem_imagens = os.path.isdir(imagens_dir) and len(os.listdir(imagens_dir)) > 0

            nome_original = os.path.splitext(uploaded_file.name)[0]
            nome_base = sanitizar_nome_arquivo(nome_original)

            if tem_imagens:
                zip_path = build_result_zip(markdown_text, tmp_dir)
                with open(zip_path, "rb") as f:
                    st.session_state.resultado_dados = f.read()
                st.session_state.resultado_nome = f"{nome_base}.zip"
                st.session_state.resultado_mime = "application/zip"
            else:
                st.session_state.resultado_dados = markdown_text.encode("utf-8")
                st.session_state.resultado_nome = f"{nome_base}.md"
                st.session_state.resultado_mime = "text/markdown"

    st.success("Conversão concluída com sucesso!")

if st.session_state.resultado_dados is not None:
    st.download_button(
        label="Baixar resultado",
        data=st.session_state.resultado_dados,
        file_name=st.session_state.resultado_nome or "resultado.md",
        mime=st.session_state.resultado_mime or "text/markdown",
    )
