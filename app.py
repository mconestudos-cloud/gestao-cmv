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
    categoria_padrao = "Outros" 
    
    if not df_config.empty:
        for _, row in df_config.iterrows():
            termo = str(row['Termo_XML']).upper()
            if termo in nome_bruto_up:
                nome_final = row['Nome_Padrao']
                fator = float(row['Fator_Conversao'])
                if 'Categoria' in row and pd.notna(row['Categoria']):
                    categoria_padrao = row['Categoria']
                break
    return nome_final, fator, categoria_padrao

def salvar_no_historico(origem, numero_nota, fornecedor, item_bruto, categoria, qtd_informada, valor_total, df_config):
    nome_padrao, fator, cat_dicionario = aplicar_padronizacao(item_bruto, df_config)
    cat_final = categoria if origem == "Manual" else cat_dicionario
    qtd_real = float(qtd_informada) * fator
    preco_kg_real = valor_total / qtd_real if qtd_real > 0 else 0
    
    df_historico = carregar_dados("Historico")
    nova_linha = pd.DataFrame([{
        "Data_Registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Origem": origem,
        "Numero_Nota": numero_nota,
        "Fornecedor": fornecedor,
        "Item_Original": item_bruto,
        "Item_Padrao": nome_padrao,
        "Quantidade_Kg": qtd_real,
        "Valor_Total": valor_total,
        "Preco_Kg_Real": preco_kg_real,
        "Categoria": cat_final
    }])
    df_final = pd.concat([df_historico, nova_linha], ignore_index=True)
    conn.update(spreadsheet=URL_PLANILHA, worksheet="Historico", data=df_final)

# --- NAVEGAÇÃO ---
menu = st.sidebar.radio("Menu", ["Lançamentos", "Configurações (Dicionário)", "Dashboard BI"])
df_config = carregar_dados("Config")
df_historico_atual = carregar_dados("Historico")

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
                    salvar_no_historico("Manual", "S/N", forn, item, cat, qtd, vlr, df_config)
                st.success(f"✅ {item} registrado!")
                st.rerun()

    with aba_xml:
        if 'uploader_key' not in st.session_state:
            st.session_state['uploader_key'] = 0

        up = st.file_uploader("Selecione o arquivo XML", type='xml', key=f"xml_up_{st.session_state['uploader_key']}")
        
        if up:
            try:
                dados = xmltodict.parse(up.read())
                emitente = dados['nfeProc']['NFe']['infNFe']['emit']['xNome']
                numero_nfe = dados['nfeProc']['NFe']['infNFe']['ide']['nNF']
                produtos = dados['nfeProc']['NFe']['infNFe']['det']
                if not isinstance(produtos, list): produtos = [produtos]
                
                # Verificação de Duplicidade Inteligente
                nota_ja_existe = False
                if not df_historico_atual.empty and 'Numero_Nota' in df_historico_atual.columns:
                    if str(numero_nfe) in df_historico_atual['Numero_Nota'].astype(str).values:
                        nota_ja_existe = True

                st.info(f"📍 Fornecedor: {emitente} | 🧾 NFe: {numero_nfe}")
                
                previa_dados = []
                for p in produtos:
                    prod = p['prod']
                    n_pad, fat, cat_padrao = aplicar_padronizacao(prod['xProd'], df_config)
                    previa_dados.append({
                        "Item Original": prod['xProd'],
                        "Item Padronizado": n_pad,
                        "Categoria": cat_padrao,
                        "Qtd Calc (Kg)": float(prod['qCom']) * fat,
                        "Valor (R$)": float(prod['vProd'])
                    })
                
                st.dataframe(pd.DataFrame(previa_dados), use_container_width=True)
                
                # Renderiza o alerta e o botão de acordo com a existência da nota
                if nota_ja_existe:
                    st.warning(f"⚠️ ATENÇÃO: A Nota Fiscal nº {numero_nfe} já consta no banco de dados. A importação irá gerar dados duplicados.")
                    botao_importar = st.button("🚨 Ignorar Alerta e Importar Duplicado")
                else:
                    botao_importar = st.button("🚀 Confirmar Importação Total")
                
                if botao_importar:
                    with st.spinner("Integrando nota ao banco de dados..."):
                        for p in produtos:
                            prod = p['prod']
                            salvar_no_historico("XML", str(numero_nfe), emitente, prod['xProd'], "XML", float(prod['qCom']), float(prod['vProd']), df_config)
                    
                    st.balloons()
                    st.success(f"✅ Nota {numero_nfe} importada com sucesso!")
                    st.session_state['uploader_key'] += 1
                    st.rerun()

            except Exception as e:
                st.error(f"Erro ao ler XML: {e}")

elif menu == "Configurações (Dicionário)":
    st.header("⚙️ Dicionário de Padronização (De/Para)")
    
    col1, col2, col3, col4 = st.columns(4)
    t_xml = col1.text_input("Termo no XML", key="conf_xml", help="Ex: TIO JOAO 5KG")
    n_pad = col2.text_input("Nome Padrão", key="conf_pad", help="Ex: Arroz Branco")
    cat_dic = col3.selectbox("Categoria", ["Carnes", "Hortifruti", "Secos", "Bebidas", "Outros"], key="conf_cat")
    f_conv = col4.number_input("Fator (Kg)", min_value=0.001, value=1.0, format="%.3f", key="conf_fator")
    
    if st.button("Adicionar Regra"):
        if t_xml and n_pad:
            nova_regra = pd.DataFrame([{"Termo_XML": t_xml, "Nome_Padrao": n_pad, "Fator_Conversao": f_conv, "Categoria": cat_dic}])
            df_atualizado = pd.concat([df_config, nova_regra], ignore_index=True)
            conn.update(spreadsheet=URL_PLANILHA, worksheet="Config", data=df_atualizado)
            st.success("Regra adicionada!")
            st.rerun()
        else:
            st.warning("Preencha o termo e o nome padrão.")
    
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
