import streamlit as st
import pandas as pd
import xmltodict
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# Configuração da página para facilitar a análise de FP&A
st.set_page_config(page_title="Gestão de CMV - Restaurante", layout="wide")
st.title("📊 Sistema de Gestão de CMV")
st.markdown("Ferramenta de automação para controle de compras e análise de custos unitários.")

# Estabelecer conexão com o Google Sheets usando as Secrets que você salvou
conn = st.connection("gsheets", type=GSheetsConnection)

# MANTENHA O LINK DA SUA PLANILHA ABAIXO
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1UdKu1R33qhJTyVjAJNfNFZYsChFcowRlzitjcooLa8/edit#gid=0"

def carregar_dados():
    """Lê os dados históricos da planilha em tempo real."""
    try:
        # ttl=0 garante que o cache não segure dados antigos após deletar linhas na planilha
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet="Historico", ttl=0)
        return df.dropna(how="all")
    except Exception as e:
        st.error("Erro ao conectar com a planilha. Verifique se o e-mail do robô é 'Editor'.")
        return pd.DataFrame(columns=['Data_Registro', 'Origem', 'Item', 'Categoria', 'Quantidade_Kg', 'Valor_Total', 'Preco_por_Kg'])

def adicionar_compra(origem, item, categoria, qtd_kg, valor_total):
    """Adiciona um novo registro ao histórico no Google Sheets."""
    df_atual = carregar_dados()
    preco_kg = valor_total / qtd_kg if qtd_kg > 0 else 0
    
    nova_linha = pd.DataFrame([{
        'Data_Registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Origem': origem,
        'Item': item,
        'Categoria': categoria,
        'Quantidade_Kg': float(qtd_kg),
        'Valor_Total': float(valor_total),
        'Preco_por_Kg': float(preco_kg)
    }])
    
    df_novo = pd.concat([df_atual, nova_linha], ignore_index=True)
    conn.update(spreadsheet=URL_PLANILHA, worksheet="Historico", data=df_novo)

# --- INTERFACE DE ENTRADA ---
aba_manual, aba_xml = st.tabs(["✍️ Registro Manual", "🧾 Importação de XML (NFe)"])

with aba_manual:
    with st.form("form_manual", clear_on_submit=True):
        c1, c2 = st.columns(2)
        item_nome = c1.text_input("Descrição do Insumo")
        categoria = c2.selectbox("Categoria", ["Carnes", "Hortifruti", "Laticínios", "Bebidas", "Secos", "Outros"])
        
        c3, c4 = st.columns(2)
        quantidade = c3.number_input("Peso Comprado (Kg)", min_value=0.001, format="%.3f")
        valor = c4.number_input("Valor Total da Nota (R$)", min_value=0.01, format="%.2f")
        
        if st.form_submit_button("Salvar no Histórico"):
            with st.spinner("Gravando dados..."):
                adicionar_compra("Manual", item_nome, categoria, quantidade, valor)
            st.success(f"Sucesso: {item_nome} registrado!")
            st.rerun()

with aba_xml:
    st.write("Arraste o arquivo .xml da nota fiscal abaixo para processar os itens automaticamente.")
    arquivo_xml = st.file_uploader("Upload XML NFe", type=['xml'])
    
    if arquivo_xml:
        try:
            dados_xml = xmltodict.parse(arquivo_xml.read())
            # Navegação na estrutura padrão da NFe brasileira
            produtos = dados_xml['nfeProc']['NFe']['infNFe']['det']
            if not isinstance(produtos, list): produtos = [produtos]
                
            st.info(f"Detectados {len(produtos)} itens nesta nota.")
            if st.button("Confirmar Importação de Todos os Itens"):
                with st.spinner("Processando lote..."):
                    for p in produtos:
                        info = p['prod']
                        adicionar_compra("XML", info['xProd'], "A Classificar", float(info['qCom']), float(info['vProd']))
                st.success("Nota fiscal integrada com sucesso!")
                st.rerun()
        except:
            st.error("Erro na leitura do XML. Certifique-se de que é um arquivo de NFe válido.")

# --- DASHBOARD DE ANÁLISE ---
st.divider()
df_resumo = carregar_dados()

if not df_resumo.empty:
    # Garantir que colunas numéricas sejam tratadas corretamente
    df_resumo['Valor_Total'] = pd.to_numeric(df_resumo['Valor_Total'])
    df_resumo['Quantidade_Kg'] = pd.to_numeric(df_resumo['Quantidade_Kg'])
    
    # Métricas Principais
    m1, m2, m3 = st.columns(3)
    total_financeiro = df_resumo['Valor_Total'].sum()
    total_peso = df_resumo['Quantidade_Kg'].sum()
    m1.metric("Gasto Total (CMV)", f"R$ {total_financeiro:,.2f}")
    m2.metric("Volume Total", f"{total_peso:,.2f} Kg")
    m3.metric("Preço Médio Global/Kg", f"R$ {(total_financeiro/total_peso):,.2f}")

    # Visão por Categoria
    st.subheader("📊 Distribuição de Custos")
    col_grafico, col_tabela = st.columns([1, 1])
    
    df_cat = df_resumo.groupby('Categoria')['Valor_Total'].sum().reset_index()
    col_grafico.bar_chart(df_cat.set_index('Categoria'))
    
    col_tabela.dataframe(df_resumo[['Data_Registro', 'Item', 'Categoria', 'Preco_por_Kg']].sort_values(by='Data_Registro', ascending=False), use_container_width=True)
else:
    st.warning("Aguardando dados para gerar indicadores financeiros.")
