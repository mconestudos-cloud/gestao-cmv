import streamlit as st
import pandas as pd
import xmltodict
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import re

st.set_page_config(page_title="Gestão de CMV Inteligente", layout="wide")

# Conexão GSheets
conn = st.connection("gsheets", type=GSheetsConnection)
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1UdKu1R33qhJTyVjAJNfNFZYsChFcowRlzitjcooLa8/edit#gid=0"

# Funções de Apoio
def carregar_dados(aba):
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl=0)
        return df.dropna(how="all")
    except:
        return pd.DataFrame()

def padronizar_item(nome_xml, df_de_para):
    """Consulta o dicionário para traduzir o nome e aplicar fator de conversão."""
    nome_xml = nome_xml.upper()
    fator = 1.0
    nome_final = nome_xml.title()
    
    if not df_de_para.empty:
        for _, row in df_de_para.iterrows():
            termo = str(row['Termo_XML']).upper()
            if termo in nome_xml:
                nome_final = row['Nome_Padrao']
                fator = float(row['Fator_Conversao'])
                break
    return nome_final, fator

# --- INTERFACE ---
menu = st.sidebar.radio("Navegação", ["Lançamentos", "Configurações (De/Para)", "Dashboard BI"])

if menu == "Configurações (De/Para)":
    st.header("⚙️ Dicionário de Padronização")
    st.info("Ensine o robô: Se o XML contiver 'ARROZ', salve como 'Arroz Branco' e multiplique por '5' (se for fardo 5kg).")
    
    df_config = carregar_dados("Config")
    
    with st.form("add_config"):
        c1, c2, c3 = st.columns(3)
        t_xml = c1.text_input("Termo no XML (ex: ARROZ)")
        n_pad = c2.text_input("Nome Padrão (ex: Arroz Branco)")
        f_conv = c3.number_input("Fator de Conversão", min_value=0.001, value=1.0, format="%.3f")
        if st.form_submit_button("Salvar Regra"):
            novo_de_para = pd.concat([df_config, pd.DataFrame([{"Termo_XML": t_xml, "Nome_Padrao": n_pad, "Fator_Conversao": f_conv}])], ignore_index=True)
            conn.update(spreadsheet=URL_PLANILHA, worksheet="Config", data=novo_de_para)
            st.success("Regra salva!")
            st.rerun()
    st.dataframe(df_config, use_container_width=True)

elif menu == "Lançamentos":
    st.header("🧾 Importação de Notas")
    df_config = carregar_dados("Config")
    arquivo = st.file_uploader("Arraste o XML aqui", type='xml')
    
    if arquivo:
        dados = xmltodict.parse(arquivo.read())
        emitente = dados['nfeProc']['NFe']['infNFe']['emit']['xNome']
        produtos = dados['nfeProc']['NFe']['infNFe']['det']
        if not isinstance(produtos, list): produtos = [produtos]
        
        st.write(f"**Fornecedor:** {emitente}")
        
        itens_processados = []
        for p in produtos:
            prod = p['prod']
            nome_original = prod['xProd']
            qtd_xml = float(prod['qCom'])
            vlr_xml = float(prod['vProd'])
            
            nome_padrao, fator = padronizar_item(nome_original, df_config)
            qtd_final = qtd_xml * fator
            
            itens_processados.append({
                "Data_Registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Fornecedor": emitente,
                "Item_Original": nome_original,
                "Item_Padrao": nome_padrao,
                "Qtd_Real": qtd_final,
                "Valor_Total": vlr_xml,
                "Preco_Kg_Real": vlr_xml / qtd_final if qtd_final > 0 else 0
            })
        
        df_previa = pd.DataFrame(itens_processados)
        st.dataframe(df_previa)
        
        if st.button("Confirmar e Salvar no Sheets"):
            df_historico = carregar_dados("Historico")
            df_final = pd.concat([df_historico, df_previa], ignore_index=True)
            conn.update(spreadsheet=URL_PLANILHA, worksheet="Historico", data=df_final)
            st.success("Dados processados e padronizados com sucesso!")

elif menu == "Dashboard BI":
    st.header("📈 Análise Estratégica de CMV")
    df = carregar_dados("Historico")
    if not df.empty:
        st.metric("Total Comprado", f"R$ {pd.to_numeric(df['Valor_Total']).sum():,.2f}")
        # Gráfico comparativo por Item_Padrao (independente da marca no XML)
        df_comp = df.groupby('Item_Padrao')['Preco_Kg_Real'].mean().reset_index()
        st.bar_chart(df_comp.set_index('Item_Padrao'))
