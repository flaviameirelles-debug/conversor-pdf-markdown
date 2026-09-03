import re
import streamlit as st
from converter import convert_pdf

st.set_page_config(page_title="Conversor de PDF para Markdown", page_icon="📄", layout="centered")
st.title("Conversor de PDF para Markdown")
st.write("Envie um PDF, converta e baixe o resultado em Markdown (com as imagens do documento já embutidas no próprio arquivo).")

if "resultado_dados" not in st.session_state:
    st.session_state.resultado_dados = None
if "resultado_nome" not in st.session_state:
    st.session_state.resultado_nome = None


def sanitizar_nome_arquivo(nome):
    import unicodedata
    nome_sem_acento = unicodedata.normalize("NFKD", nome)
    nome_sem_acento = "".join(c for c in nome_sem_acento if not unicodedata.combining(c))
    nome_limpo = re.sub(r"[^a-zA-Z0-9_-]+", "_", nome_sem_acento)
    nome_limpo = re.sub(r"_+", "_", nome_limpo).strip("_")
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

        def progress_cb(pagina, total):
            pass

        markdown_text, tem_imagens = convert_pdf(pdf_bytes, progress_callback=progress_cb)

        nome_original = uploaded_file.name.rsplit(".", 1)[0]
        nome_base = sanitizar_nome_arquivo(nome_original)

        st.session_state.resultado_dados = markdown_text.encode("utf-8")
        st.session_state.resultado_nome = f"{nome_base}.md"

    if tem_imagens:
        st.success("Conversão concluída com sucesso! As imagens foram embutidas dentro do próprio arquivo .md.")
    else:
        st.success("Conversão concluída com sucesso!")

if st.session_state.resultado_dados is not None:
    st.download_button(
        label="Baixar resultado (.md)",
        data=st.session_state.resultado_dados,
        file_name=st.session_state.resultado_nome or "resultado.md",
        mime="text/markdown",
    )
