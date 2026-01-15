import pymongo
import pandas as pd
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz

# --- CONFIGURAÇÕES GLOBAIS ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "faturamento_db"
COLLECTION_NAME = "notas_fiscais"
OUTPUT_FOLDER = 'output'

# [ADAPTAÇÃO] Removida "Rio de Janeiro" e definida ordem fixa
FILIAIS_ORDEM = ["Juiz de Fora", "Vale Aço"] 

# [ADAPTAÇÃO] Ano de referência para o relatório anual
ANO_REFERENCIA = 2025

FUSO_HORARIO = pytz.timezone('America/Sao_Paulo')

# Paleta de Cores
COR_PRINCIPAL = (0, 63, 92)
COR_SECUNDARIA = (47, 79, 79)
COR_FUNDO_LINHA = (240, 240, 240)
CORES_GRAFICOS_EVOLUCAO = ["#003f5c", "#ff6361", "#ffa600", "#7a5195", "#bc5090", "#ef5675"]

# --- FUNÇÕES DE BANCO DE DADOS E GRÁFICOS ---

def get_data_from_mongo():
    """
    Busca os dados do MongoDB e converte datas.
    """
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        df = pd.DataFrame(list(collection.find()))
        if df.empty:
            print("A coleção no MongoDB está vazia.")
            return None
        
        # Converte datas para datetime e ajusta fuso
        df['emissao'] = pd.to_datetime(df['emissao'])
        
        # Verifica se já tem timezone, se não tiver, localiza
        if df['emissao'].dt.tz is None:
            df['emissao'] = df['emissao'].dt.tz_localize('UTC').dt.tz_convert(FUSO_HORARIO)
        else:
            df['emissao'] = df['emissao'].dt.tz_convert(FUSO_HORARIO)
            
        client.close()
        return df
    except Exception as e:
        print(f"Erro ao conectar ou buscar dados no MongoDB: {e}")
        return None

def create_bar_chart(data, title, filename):
    if data.empty or data.sum() == 0:
        fig, ax = plt.subplots(figsize=(10, 2))
        ax.text(0.5, 0.5, 'Sem dados para o período', ha='center', va='center')
        ax.set_xticks([]); ax.set_yticks([])
    else:
        # Garante que apenas as filiais desejadas apareçam e na ordem certa
        data = data.reindex(FILIAIS_ORDEM, fill_value=0)
        
        fig, ax = plt.subplots(figsize=(10, 3)) # Aumentei um pouco a altura
        bars = ax.barh(data.index, data.values, color=CORES_GRAFICOS_EVOLUCAO[:len(FILIAIS_ORDEM)])
        ax.set_xlabel('Valor Faturado (R$)')
        ax.set_title(title, loc='left', color=[c/255 for c in COR_SECUNDARIA], fontsize=10)
        ax.xaxis.set_major_formatter(mticker.StrMethodFormatter('R$ {x:,.2f}'))
        ax.set_xlim(left=0)
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        for bar in bars:
            width = bar.get_width()
            if width > 0:
                ax.text(width * 1.01, bar.get_y() + bar.get_height()/2, f'R$ {width:,.2f}', va='center', fontsize=9)
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

def create_line_chart(data_dict, title, filename, is_multiple_lines=False):
    fig, ax = plt.subplots(figsize=(10, 4))
    if is_multiple_lines:
        if not data_dict:
             ax.text(0.5, 0.5, 'Dados insuficientes para gerar evolução por filial', ha='center', va='center')
        else:
            for i, (label, data) in enumerate(data_dict.items()):
                if not data.empty:
                    ax.plot(data.index, data.values, marker='o', label=label, color=CORES_GRAFICOS_EVOLUCAO[i % len(CORES_GRAFICOS_EVOLUCAO)])
                    for x, y in zip(data.index, data.values):
                        if y > 0:
                            ax.text(x, y, f'R$ {y:,.0f}', ha='center', va='bottom', fontsize=7, color='black')
            ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
            plt.subplots_adjust(right=0.75)
    else:
        data = data_dict
        if data.empty:
            ax.text(0.5, 0.5, 'Dados insuficientes para gerar evolução', ha='center', va='center')
        else:
            ax.plot(data.index, data.values, marker='o', color=f"#{COR_PRINCIPAL[0]:02x}{COR_PRINCIPAL[1]:02x}{COR_PRINCIPAL[2]:02x}")
            for x, y in zip(data.index, data.values):
                if y > 0:
                    ax.text(x, y, f'R$ {y:,.0f}', ha='center', va='bottom', fontsize=7, color='black')
    ax.set_title(title, loc='left', color=[c/255 for c in COR_SECUNDARIA])
    ax.set_ylabel('Valor Faturado (R$)')
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter('R$ {x:,.0f}'))
    ax.set_ylim(bottom=0)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()


# --- CLASSE PARA GERAÇÃO DO PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.set_text_color(*COR_PRINCIPAL)
        # [ADAPTAÇÃO] Título alterado para Anual
        self.cell(0, 10, f'Relatório Anual de Faturamento - {ANO_REFERENCIA}', 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 5, f'Gerado em: {datetime.now(FUSO_HORARIO).strftime("%d/%m/%Y %H:%M:%S")}', 0, 1, 'C')
        self.ln(5)
        self.set_draw_color(*COR_PRINCIPAL)
        self.cell(0, 0, '', 'T', 1)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', 0, 0, 'C')

    def create_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(*COR_SECUNDARIA)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)

    def create_kpi_box(self, title, value, x, y):
        self.set_xy(x, y)
        self.set_font('Arial', 'B', 10)
        self.set_fill_color(*COR_PRINCIPAL)
        self.set_text_color(255, 255, 255)
        self.cell(65, 8, title, 0, 0, 'C', fill=True)
        
        self.set_xy(x, y + 8)
        self.set_font('Arial', '', 12)
        self.set_text_color(0, 0, 0)
        self.set_draw_color(220, 220, 220)
        formatted_value = f'R$ {value:,.2f}' if isinstance(value, (int, float)) else str(value)
        self.cell(65, 12, formatted_value, 1, 1, 'C')

    def create_styled_table(self, headers, data, column_widths):
        self.set_font('Arial', 'B', 9)
        self.set_fill_color(*COR_PRINCIPAL)
        self.set_text_color(255, 255, 255)
        self.set_draw_color(255, 255, 255)
        
        for i, header in enumerate(headers):
            self.cell(column_widths[i], 8, header, 1, 0, 'C', fill=True)
        self.ln()

        self.set_font('Arial', '', 8)
        self.set_text_color(0, 0, 0)
        fill = False
        for row in data:
            self.set_fill_color(*COR_FUNDO_LINHA if fill else (255, 255, 255))
            for i, item in enumerate(row):
                self.cell(column_widths[i], 7, str(item), 'LR', 0, 'L' if i == 2 else 'C', fill=True)
            self.ln()
            fill = not fill
        self.cell(sum(column_widths), 0, '', 'T')


# --- FUNÇÃO PRINCIPAL ---

def main():
    print(f"Iniciando geração do relatório ANUAL de faturamento ({ANO_REFERENCIA})...")
    df = get_data_from_mongo()
    if df is None: return

    # Filtra apenas as filiais desejadas antes de qualquer cálculo
    df = df[df['filial_nome'].isin(FILIAIS_ORDEM)]

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    # Define o período do ano selecionado
    inicio_ano = datetime(ANO_REFERENCIA, 1, 1, 0, 0, 0).astimezone(FUSO_HORARIO)
    fim_ano = datetime(ANO_REFERENCIA, 12, 31, 23, 59, 59).astimezone(FUSO_HORARIO)
    
    # Filtra os DataFrames
    df_ano_completo = df[(df['emissao'] >= inicio_ano) & (df['emissao'] <= fim_ano)]
    
    # Para comparação, vamos pegar o total do ano anterior também
    inicio_ano_anterior = inicio_ano - relativedelta(years=1)
    fim_ano_anterior = fim_ano - relativedelta(years=1)
    df_ano_anterior = df[(df['emissao'] >= inicio_ano_anterior) & (df['emissao'] <= fim_ano_anterior)]

    pdf = PDF('P', 'mm', 'A4')
    pdf.alias_nb_pages()
    
    # --- PÁGINA 1: DASHBOARD ANUAL ---
    pdf.add_page()
    pdf.create_title(f'Dashboard Consolidado - {ANO_REFERENCIA}')
    
    total_ano = df_ano_completo['valor_total_nota'].sum()
    total_ano_anterior = df_ano_anterior['valor_total_nota'].sum()
    media_mensal = total_ano / 12 if total_ano > 0 else 0

    pdf.create_kpi_box(f'Total Faturado {ANO_REFERENCIA}', total_ano, x=10, y=45)
    pdf.create_kpi_box(f'Total Faturado {ANO_REFERENCIA - 1}', total_ano_anterior, x=78, y=45)
    pdf.create_kpi_box('Média Mensal (Est.)', media_mensal, x=146, y=45)
    pdf.ln(30)
    
    print("Gerando gráficos da página 1...")
    
    # Gráfico 1: Total por filial no ano
    faturamento_filial_ano = df_ano_completo.groupby('filial_nome')['valor_total_nota'].sum()
    create_bar_chart(faturamento_filial_ano, f'Faturamento Total por Filial ({ANO_REFERENCIA})', 'chart_p1_1.png')
    pdf.image('chart_p1_1.png', x=10, w=190)
    
    # Gráfico 2: Comparativo com Ano Anterior (se houver dados)
    faturamento_filial_ano_ant = df_ano_anterior.groupby('filial_nome')['valor_total_nota'].sum()
    create_bar_chart(faturamento_filial_ano_ant, f'Comparativo: Faturamento ({ANO_REFERENCIA - 1})', 'chart_p1_2.png')
    pdf.image('chart_p1_2.png', x=10, w=190)

    # --- PÁGINA 2: MAIORES VENDAS DO ANO ---
    pdf.add_page()
    pdf.create_title('Top 10 Notas Fiscais do Ano')
    for filial in FILIAIS_ORDEM:
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(*COR_SECUNDARIA)
        pdf.cell(0, 10, filial, 0, 1)
        # Filtra top 10 do ano inteiro
        df_filial = df_ano_completo[df_ano_completo['filial_nome'] == filial].nlargest(10, 'valor_total_nota')
        
        if df_filial.empty:
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 10, 'Nenhuma nota fiscal encontrada para esta filial neste ano.', 0, 1)
        else:
            headers = ['Emissão', 'Nota Fiscal', 'Cliente', 'Valor Total']
            column_widths = [25, 25, 90, 30]
            table_data = []
            for _, row in df_filial.iterrows():
                table_data.append([row['emissao'].strftime('%d/%m/%Y'), row['numero_nota'], str(row['EMPRESA'])[:50], f"R$ {row['valor_total_nota']:,.2f}"])
            pdf.create_styled_table(headers, table_data, column_widths)
        pdf.ln(5)

    # --- PÁGINA 3: EVOLUÇÃO MENSAL (JANEIRO A DEZEMBRO) ---
    pdf.add_page()
    pdf.create_title(f'Evolução Mensal - {ANO_REFERENCIA}')
    
    # Garante que mostraremos apenas os meses do ano de referência
    df_evolucao = df_ano_completo.copy()
    
    if not df_evolucao.empty:
        # Gráfico 1: Evolução Geral
        evolucao_geral = df_evolucao.set_index('emissao').resample('MS')['valor_total_nota'].sum()
        # Formata o índice para mostrar Mês
        evolucao_geral.index = evolucao_geral.index.strftime('%b')
        
        print("Gerando gráfico de evolução geral...")
        create_line_chart(evolucao_geral, f'Tendência Mensal Geral ({ANO_REFERENCIA})', 'chart_p3_1.png', is_multiple_lines=False)
        pdf.image('chart_p3_1.png', x=10, w=190)
        pdf.ln(5)

        # Gráfico 2: Evolução por Filial
        print("Gerando gráfico de evolução por filial...")
        evolucao_por_filial = {}
        for filial_nome in FILIAIS_ORDEM:
            df_filial_evolucao = df_evolucao[df_evolucao['filial_nome'] == filial_nome]
            if not df_filial_evolucao.empty:
                data_filial = df_filial_evolucao.set_index('emissao').resample('MS')['valor_total_nota'].sum()
                data_filial.index = data_filial.index.strftime('%b')
                evolucao_por_filial[filial_nome] = data_filial
        
        if evolucao_por_filial:
            create_line_chart(evolucao_por_filial, f'Performance Mensal por Filial ({ANO_REFERENCIA})', 'chart_p3_2.png', is_multiple_lines=True)
            pdf.image('chart_p3_2.png', x=10, w=190)
    else:
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 10, f'Não há dados suficientes em {ANO_REFERENCIA} para gerar gráficos de evolução.', 0, 1)
    
    report_filename = f"Relatorio_Anual_Faturamento_{ANO_REFERENCIA}.pdf"
    full_path = os.path.join(OUTPUT_FOLDER, report_filename)
    pdf.output(full_path)
    print(f"Relatório final salvo com sucesso em: {full_path}")

    for file in os.listdir('.'):
        if file.startswith('chart_') and file.endswith('.png'):
            os.remove(file)
    print("Arquivos de imagem temporários removidos.")

if __name__ == '__main__':
    main()