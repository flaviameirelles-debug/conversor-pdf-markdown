# Conversor de PDF para Markdown

Aplicação de tela única (Streamlit) para professores converterem PDF em Markdown, sem precisar de terminal ou programação.

## Como executar localmente

pip install -r requirements.txt
streamlit run app.py

O navegador abrirá automaticamente em http://localhost:8501.

## Como publicar para os professores usarem (sem instalar nada)

A forma mais simples é o Streamlit Community Cloud (gratuito):

1. Suba esta pasta (app.py, converter.py, requirements.txt) para um repositório no GitHub.
2. Acesse share.streamlit.io, conecte o repositório e aponte para app.py.
3. O Streamlit gera um link público — é só compartilhar esse link com os professores.

## Uso

1. Arraste o PDF ou clique em "Selecionar PDF".
2. Clique em "Converter para Markdown".
3. Aguarde a mensagem de conclusão.
4. Clique em "Baixar resultado" para obter o Markdown (em .md, ou em .zip junto com as imagens quando o PDF tiver imagens).
