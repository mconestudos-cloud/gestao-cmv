import streamlit as st
import pandas as pd
import xmltodict
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Gestão de CMV - FP&A", layout="wide")
st.title("📊 Gestão de CMV e Insumos")
st.markdown("Otimização da entrada de notas, cálculo de CMV e histórico no Google Sheets.")

# Estabelecer conexão com o Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Substitua pela URL completa da sua planilha do Google Sheets
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1UdKu1R33qhJTyVjAJNfbNFZYsChFcowRlzitjcooLa8/edit?gid=0#gid=0"

def carregar_dados():
    """Carrega os dados do Google Sheets."""
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet="Historico", ttl=0)
        return df.dropna(how="all") # Remove linhas totalmente vazias
    except Exception as e:
        st.error("Erro ao carregar dados. Verifique a conexão ou a URL da planilha.")
        return pd.DataFrame(columns=['Data_Registro', 'Origem', 'Item', 'Categoria', 'Quantidade_Kg', 'Valor_Total', 'Preco_por_Kg'])

def adicionar_compra(origem, item, categoria, qtd_kg, valor_total):
    """Lê a planilha, adiciona a nova linha e atualiza o Google Sheets."""
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

# --- INTERFACE DE INSERÇÃO DE DADOS ---
aba_manual, aba_xml = st.tabs(["✍️ Input Manual", "🧾 Importar XML (NFe)"])

with aba_manual:
    with st.form("form_manual", clear_on_submit=True):
        col1, col2 = st.columns(2)
        item_nome = col1.text_input("Nome do Insumo")
        categoria = col2.selectbox("Categoria", ["Carnes", "Hortifruti", "Laticínios", "Bebidas", "Secos", "Outros"])
        
        col3, col4 = st.columns(2)
        quantidade = col3.number_input("Quantidade (Kg)", min_value=0.01, step=0.1)
        valor = col4.number_input("Valor Total (R$)", min_value=0.01, step=1.0)
        
        submit = st.form_submit_button("Registrar Compra")
        if submit:
            with st.spinner("Salvando no Google Sheets..."):
                adicionar_compra("Manual", item_nome, categoria, quantidade, valor)
            st.success(f"✅ {item_nome} salvo com sucesso!")
            st.rerun()

with aba_xml:
    st.info("Faça o upload do XML da Nota Fiscal Eletrônica (NFe).")
    arquivo_xml = st.file_uploader("Selecione o arquivo XML", type=['xml'])
    
    if arquivo_xml is not None:
        try:
            dict_xml = xmltodict.parse(arquivo_xml.read())
            produtos = dict_xml['nfeProc']['NFe']['infNFe']['det']
            
            if not isinstance(produtos, list):
                produtos = [produtos]
                
            st.write(f"**{len(produtos)} itens encontrados na nota.**")
            
            with st.spinner("Processando e salvando itens no Google Sheets..."):
                for prod in produtos:
                    prod_info = prod['prod']
                    nome_prod = prod_info['xProd']
                    qtd = float(prod_info['qCom']) 
                    vlr = float(prod_info['vProd'])
                    adicionar_compra("XML", nome_prod, "A Classificar", qtd, vlr)
                
            st.success("✅ Nota Fiscal salva no histórico com sucesso!")
        except Exception as e:
            st.error("Erro ao processar o XML. Verifique se é um XML de NFe válido.")

# --- SEÇÃO DE ANÁLISE E FP&A ---
st.divider()
st.header("📈 Dashboard de CMV - Histórico Consolidado")

df = carregar_dados()

if not df.empty:
    # Conversão de tipos para garantir os cálculos matemáticos
    df['Valor_Total'] = pd.to_numeric(df['Valor_Total'], errors='coerce')
    df['Quantidade_Kg'] = pd.to_numeric(df['Quantidade_Kg'], errors='coerce')
    
    total_gasto = df['Valor_Total'].sum()
    total_kg = df['Quantidade_Kg'].sum()
    
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Custo Total Acumulado", f"R$ {total_gasto:,.2f}")
    col_m2.metric("Volume Comprado", f"{total_kg:,.2f} Kg")
    col_m3.metric("Custo Médio Global / Kg", f"R$ {(total_gasto/total_kg):,.2f}" if total_kg > 0 else "R$ 0,00")
    
    st.subheader("Custos por Categoria")
    df_categoria = df.groupby('Categoria').agg(
        Total_Gasto=('Valor_Total', 'sum'),
        Total_Kg=('Quantidade_Kg', 'sum')
    ).reset_index()
    df_categoria['Preço_Médio/Kg'] = df_categoria['Total_Gasto'] / df_categoria['Total_Kg']
    
    st.dataframe(df_categoria.style.format({
        'Total_Gasto': 'R$ {:.2f}',
        'Total_Kg': '{:.2f} kg',
        'Preço_Médio/Kg': 'R$ {:.2f}'
    }), use_container_width=True)
    
    st.subheader("Detalhamento de Entradas (Google Sheets)")
    st.dataframe(df.style.format({
        'Valor_Total': 'R$ {:.2f}',
        'Preco_por_Kg': 'R$ {:.2f}'
    }), use_container_width=True)
else:
    st.warning("A planilha está vazia. Adicione insumos manualmente ou importe um XML para começar.")
