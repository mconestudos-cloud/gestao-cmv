import streamlit as st
import pandas as pd
import xmltodict
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Gestão de CMV - BI", layout="wide")
st.title("📊 BI de Compras & CMV")

# Conexão com Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1UdKu1R33qhJTyVjAJNfNFZYsChFcowRlzitjcooLa8/edit#gid=0"

def carregar_dados():
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet="Historico", ttl=0)
        df = df.dropna(how="all")
        df['Data_Registro'] = pd.to_datetime(df['Data_Registro'])
        df['Valor_Total'] = pd.to_numeric(df['Valor_Total'])
        df['Quantidade_Kg'] = pd.to_numeric(df['Quantidade_Kg'])
        df['Preco_por_Kg'] = pd.to_numeric(df['Preco_por_Kg'])
        return df
    except:
        return pd.DataFrame(columns=['Data_Registro', 'Origem', 'Fornecedor', 'Item', 'Categoria', 'Quantidade_Kg', 'Valor_Total', 'Preco_por_Kg'])

def adicionar_compra(origem, fornecedor, item, categoria, qtd_kg, valor_total):
    df_atual = carregar_dados()
    preco_kg = valor_total / qtd_kg if qtd_kg > 0 else 0
    nova_linha = pd.DataFrame([{
        'Data_Registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Origem': origem, 
        'Fornecedor': fornecedor, # Campo novo adicionado aqui
        'Item': item, 
        'Categoria': categoria,
        'Quantidade_Kg': float(qtd_kg), 
        'Valor_Total': float(valor_total), 
        'Preco_por_Kg': float(preco_kg)
    }])
    df_novo = pd.concat([df_atual, nova_linha], ignore_index=True)
    conn.update(spreadsheet=URL_PLANILHA, worksheet="Historico", data=df_novo)

# --- NAVEGAÇÃO ---
menu = st.sidebar.radio("Navegação", ["Lançamentos", "Análise de Preços", "Dashboard Geral"])

if menu == "Lançamentos":
    aba_m, aba_x = st.tabs(["✍️ Manual", "🧾 XML"])
    with aba_m:
        with st.form("fm"):
            col_forn, col_item = st.columns(2)
            forn = col_forn.text_input("Fornecedor") # Input do fornecedor
            it = col_item.text_input("Item/Insumo")
            
            c1, c2 = st.columns(2)
            cat = c1.selectbox("Categoria", ["Carnes", "Hortifruti", "Bebidas", "Outros"])
            q = c2.number_input("Quantidade (Kg)", min_value=0.01)
            
            v = st.number_input("Valor Total (R$)", min_value=0.01)
            
            if st.form_submit_button("Salvar Registro"):
                adicionar_compra("Manual", forn, it, cat, q, v)
                st.success("Registrado com sucesso!")
                st.rerun()
    
    with aba_x:
        up = st.file_uploader("Upload XML NFe", type='xml')
        if up:
            try:
                dict_xml = xmltodict.parse(up.read())
                nome_fornecedor = dict_xml['nfeProc']['NFe']['infNFe']['emit']['xNome']
                produtos = dict_xml['nfeProc']['NFe']['infNFe']['det']
                if not isinstance(produtos, list): produtos = [produtos]
                
                st.warning(f"Fornecedor Identificado: {nome_fornecedor}")
                if st.button("Importar Itens desta Nota"):
                    for p in produtos:
                        info = p['prod']
                        adicionar_compra("XML", nome_fornecedor, info['xProd'], "A Classificar", float(info['qCom']), float(info['vProd']))
                    st.success("Nota importada!")
                    st.rerun()
            except:
                st.error("Erro ao ler XML.")

elif menu == "Análise de Preços":
    st.header("📈 Inteligência de Compras")
    df = carregar_dados()
    if not df.empty:
        # Filtro de Item
        itens = df['Item'].unique()
        sel = st.selectbox("Selecione o Insumo:", itens)
        df_item = df[df['Item'] == sel].sort_values('Data_Registro')
        
        # Comparativo entre fornecedores
        st.subheader(f"Quem vende {sel} mais barato?")
        df_comp = df_item.groupby('Fornecedor')['Preco_por_Kg'].mean().reset_index()
        st.bar_chart(df_comp.set_index('Fornecedor'))
        
        st.write("Histórico de compras deste item:")
        st.table(df_item[['Data_Registro', 'Fornecedor', 'Preco_por_Kg']])

elif menu == "Dashboard Geral":
    df = carregar_dados()
    if not df.empty:
        st.subheader("Resumo Financeiro")
        st.dataframe(df.sort_values('Data_Registro', ascending=False), use_container_width=True)
