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
        # Removido st.form para evitar submissão pelo Enter
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
            else:
                st.warning("Preencha o fornecedor e o item.")

    with aba_xml:
        up = st.file_uploader("Selecione o arquivo XML", type='xml')
        if up:
            try:
                dados = xmltodict.parse(up.read())
                emitente = dados['nfeProc']['NFe']['infNFe']['emit']['xNome']
                produtos = dados['nfeProc']['NFe']['infNFe']['det']
                if not isinstance(produtos, list): produtos = [produtos]
                st.info(f"Fornecedor: {emitente}")
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
                if st.button("Confirmar Importação Total"):
                    for p in produtos:
                        prod = p['prod']
                        salvar_no_historico("XML", emitente, prod['xProd'], "A Classificar", float(prod['qCom']), float(prod['vProd']), df_config)
                    st.success("Nota importada com sucesso!")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao ler XML: {e}")

elif menu == "Configurações (Dicionário)":
    st.header("⚙️ Dicionário de Padronização (De/Para)")
    # Removido st.form aqui também
    col1, col2, col3 = st.columns(3)
    t_xml = col1.text_input("Termo no XML/Manual (ex: TIO JOAO 5KG)", key="conf_xml")
    n_pad = col2.text_input("Nome Padrão (ex: Arroz Branco)", key="conf_pad")
    f_conv = col3.number_input("Peso do Pacote (Kg)", min_value=0.001, value=1.0, format="%.3f", key="conf_fator")
    
    if st.button("Adicionar Regra"):
        if t_xml and n_pad:
            nova_regra = pd.concat([df_config, pd.DataFrame([{"Termo_XML": t_xml, "Nome_Padrao": n_pad, "Fator_Conversao": f_conv}])], ignore_index=True)
            conn.update(spreadsheet=URL_PLANILHA, worksheet="Config", data=nova_regra)
            st.success("Regra adicionada!")
            st.rerun()
        else:
            st.warning("Preencha todos os campos da regra.")
    
    if not df_config.empty:
        st.table(df_config)

elif menu == "Dashboard BI":
    st.header("📈 Análise de CMV & Histórico")
    df = carregar_dados("Historico")
    if not df.empty:
        df['Valor_Total'] = pd.to_numeric(df['Valor_Total'])
        df['Preco_Kg_Real'] = pd.to_numeric(df['Preco_Kg_Real'])
        st.metric("Total Investido", f"R$ {df['Valor_Total'].sum():,.2f}")
        st.subheader("Custo Médio por Quilo (Padronizado)")
        df_comp = df.groupby('Item_Padrao')['Preco_Kg_Real'].mean().reset_index()
        st.bar_chart(df_comp.set_index('Item_Padrao'))
        st.dataframe(df.sort_values("Data_Registro", ascending=False), use_container_width=True)
