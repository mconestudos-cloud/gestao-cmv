import streamlit as st
import pandas as pd
import xmltodict
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Gestão de CMV Inteligente", layout="wide")
st.title("📊 BI de Compras - Lançamentos & Padronização")

# Conexão GSheets
conn = st.connection("gsheets", type=GSheetsConnection)
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1UdKu1R33qhJTyVjAJNfNFZYsChFcowRlzitjcooLa8/edit#gid=0"

# --- FUNÇÕES DE APOIO ---
def carregar_dados(aba):
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl=0)
        return df.dropna(how="all")
    except:
        return pd.DataFrame()

def aplicar_padronizacao(nome_bruto, df_config):
    """Verifica se o item existe no dicionário e aplica o fator de conversão."""
    nome_bruto_up = str(nome_bruto).upper()
    nome_final = nome_bruto.title()
    fator = 1.0
    
    if not df_config.empty:
        for _, row in df_config.iterrows():
            termo = str(row['Termo_XML']).upper()
            if termo in nome_bruto_up:
                nome_final = row['Nome_Padrao']
                fator = float(row['Fator_Conversao'])
                break
    return nome_final, fator

def salvar_no_historico(origem, fornecedor, item_bruto, categoria, qtd_informada, valor_total, df_config):
    """Processa a padronização e salva no Sheets."""
    nome_padrao, fator = aplicar_padronizacao(item_bruto, df_config)
    qtd_real = float(qtd_informada) * fator
    preco_kg_real = valor_total / qtd_real if qtd_real > 0 else 0
    
    df_historico = carregar_dados("Historico")
    nova_linha = pd.DataFrame([{
        "Data_Registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Origem": origem,
        "Fornecedor": fornecedor,
        "Item_Original": item_bruto,
        "Item_Padrao": nome_padrao,
        "Quantidade_Kg": qtd_real,
        "Valor_Total": valor_total,
        "Preco_Kg_Real": preco_kg_real,
        "Categoria": categoria
    }])
    
    df_final = pd.concat([df_historico, nova_linha], ignore_index=True)
    conn.update(spreadsheet=URL_PLANILHA, worksheet="Historico", data=df_final)

# --- NAVEGAÇÃO ---
menu = st.sidebar.radio("Menu", ["Lançamentos", "Configurações (Dicionário)", "Dashboard BI"])

df_config = carregar_dados("Config")

if menu == "Lançamentos":
    aba_manual, aba_xml = st.tabs(["✍️ Cadastro Manual", "🧾 Importar XML (NFe)"])
    
    with aba_manual:
        with st.form("form_manual", clear_on_submit=True):
            c1, c2 = st.columns(2)
            forn = c1.text_input("Fornecedor / Loja")
            item = c2.text_input("Item (Ex: Arroz Tio Joao 5kg)")
            
            c3, c4, c5 = st.columns(3)
            cat = c3.selectbox("Categoria", ["Carnes", "Hortifruti", "Secos", "Bebidas", "Outros"])
            qtd = c4.number_
