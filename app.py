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
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1UdKu1R33qhJTyVjAJNfbNFZYsChFcowRlzitjcooLa8/edit?gid=113280754#gid=113280754"

# --- FUNÇÕES DE APOIO ---
def carregar_dados(aba):
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl=0)
        return df.dropna(how="all")
    except:
        return pd.DataFrame()

def aplicar_padronizacao(nome_bruto, df_config):
    nome_bruto_up = str(nome_bruto).upper()
    nome_final = str(nome_bruto).title()
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
        st.subheader("Novo Registro Manual")
        c1, c2 = st.columns(2)
        forn = c1.text_input("Fornecedor / Loja", key="manual_forn")
        item = c2.text_input("Item (Ex: Arroz Tio Joao 5kg)", key="manual_item")
        
        c3, c4, c5 = st.columns(3)
        cat = c3.selectbox("Categoria", ["Carnes", "Hortifruti", "Secos", "Bebidas", "Outros"], key="manual_cat")
        qtd = c4.number_input("Qtd (Unidades/Fardos)", min_value=0.01, step=1.0, key="manual_qtd")
        vlr = c5.number_input("Valor Total (R$)", min_value=0.01, key="manual_vlr")
        
        if st.button("Registrar Compra"):
            if forn and item:
                with st.spinner("Gravando..."):
                    salvar_no_historico("Manual", forn, item, cat, qtd, vlr, df_config)
                st.success(f"✅ {item} registrado!")
                st.rerun()

    with aba_xml:
        # Chave dinâmica para forçar o reset do uploader após o uso
        if 'uploader_key' not in st.session_state:
            st.session_state['uploader_key'] = 0

        up = st.file_uploader("Selecione o arquivo XML", type='xml', key=f"xml_up_{st.session_state['uploader_key']}")
        
        if up:
            try:
                dados = xmltodict.parse(up.read())
                emitente = dados['nfeProc']['NFe']['infNFe']['emit']['xNome']
                produtos = dados['nfeProc']['NFe']['infNFe']['det']
                if not isinstance(produtos, list): produtos = [produtos]
                
                st.info(f"📍 Fornecedor: {emitente}")
                
                previa_dados = []
                for p in produtos:
                    prod = p['prod']
                    n_pad, fat = aplicar_padronizacao(prod['xProd'], df_config)
                    previa_dados.append({
                        "Item Original": prod['xProd'],
                        "Item Padronizado": n_pad,
                        "Qtd Calc (Kg)": float(prod['qCom']) * fat,
                        "Valor (R$)": float(prod['vProd'])
                    })
                
                st.dataframe(pd.DataFrame(previa_dados), use_container_width=True)
                
                if st.button("🚀 Confirmar Importação Total"):
                    with st.spinner("Integrando nota ao banco de dados..."):
                        for p in produtos:
                            prod = p['prod']
                            salvar_no_historico("XML", emitente, prod['xProd'], "A Classificar", float(prod['qCom']), float(prod['vProd']), df_config)
                    
                    # Logica para limpar o campo e mostrar sucesso
                    st.balloons() # Feedback visual comemorativo
                    st.success("✅ Importação concluída! Os dados já estão no Dashboard.")
                    
                    # Muda a chave do uploader para resetar o campo vazio
                    st.session_state['uploader_key'] += 1
                    st.rerun()

            except Exception as e:
                st.error(f"Erro ao ler XML: {e}")
# ... (O restante do código de Configurações e Dashboard permanece igual)
