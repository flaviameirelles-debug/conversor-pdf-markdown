import os
import tempfile

import streamlit as st

from converter import convert_pdf, build_result_zip

st.set_page_config(page_title="Conversor de PDF para Markdown", page_icon="📄", layout="centered")

st.title("Conversor de PDF para Markdown")
st.write("Envie um PDF, converta e baixe o resultado em Markdown (com as imagens do documento).")

if "resultado_zip" not in st.session_state:
    st.session_state.resultado_zip = None
if "resultado_nome" not in st.session_state:
    st.session_state.resultado_nome = None

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
            zip_path = build_result_zip(markdown_text, tmp_dir)

            with open(zip_path, "rb") as f:
                st.session_state.resultado_zip = f.read()

        nome_base = os.path.splitext(uploaded_file.name)[0]
        st.session_state.resultado_nome = f"{nome_base}.zip"

    st.success("Conversão concluída com sucesso!")

if st.session_state.resultado_zip is not None:
    st.download_button(
        label="Baixar resultado",
        data=st.session_state.resultado_zip,
        file_name=st.session_state.resultado_nome or "resultado.zip",
        mime="application/zip",
    )
