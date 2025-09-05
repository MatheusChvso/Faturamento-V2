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
FILIAIS_ORDEM = ["Juiz de Fora", "Vale Aço", "Rio de Janeiro"]
FUSO_HORARIO = pytz.timezone('America/Sao_Paulo')

# Paleta de Cores
COR_PRINCIPAL = (0, 63, 92)
COR_SECUNDARIA = (47, 79, 79)
COR_FUNDO_LINHA = (240, 240, 240)
CORES_GRAFICOS_EVOLUCAO = ["#003f5c", "#ff6361", "#ffa600", "#7a5195", "#bc5090", "#ef5675"]

# --- FUNÇÕES DE BANCO DE DADOS E GRÁFICOS ---

def get_data_from_mongo():
    """
    Busca os dados do MongoDB. Esta é a versão final e correta que assume
    que os dados no banco foram carregados corretamente.
    """
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        df = pd.DataFrame(list(collection.find()))
        if df.empty:
            print("A coleção no MongoDB está vazia.")
            return None
        # Pymongo lê as datas como UTC. Apenas precisamos convertê-las para o nosso fuso.
        df['emissao'] = pd.to_datetime(df['emissao']).dt.tz_convert(FUSO_HORARIO)
        client.close()
        return df
    except Exception as e:
        print(f"Erro ao conectar ou buscar dados no MongoDB: {e}")
        return None

# Funções create_bar_chart e create_line_chart permanecem as mesmas da última versão.
def create_bar_chart(data, title, filename):
    if data.empty or data.sum() == 0:
        fig, ax = plt.subplots(figsize=(10, 2))
        ax.text(0.5, 0.5, 'Sem dados para o período', ha='center', va='center')
        ax.set_xticks([]); ax.set_yticks([])
    else:
        data = data.reindex(FILIAIS_ORDEM, fill_value=0)
        fig, ax = plt.subplots(figsize=(10, 2))
        bars = ax.barh(data.index, data.values, color=CORES_GRAFICOS_EVOLUCAO)
        ax.set_xlabel('Valor Faturado (R$)')
        ax.set_title(title, loc='left', color=[c/255 for c in COR_SECUNDARIA], fontsize=10)
        ax.xaxis.set_major_formatter(mticker.StrMethodFormatter('R$ {x:,.2f}'))
        ax.set_xlim(left=0)
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        for bar in bars:
            width = bar.get_width()
            if width > 0:
                ax.text(width * 1.01, bar.get_y() + bar.get_height()/2, f'R$ {width:,.2f}', va='center', fontsize=8)
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


# --- CLASSE PARA GERAÇÃO DO PDF (sem alterações) ---
class PDF(FPDF):
    def header(self):
        # self.image('seu_logo.png', 10, 8, 33) # Descomente e adicione seu logo aqui
        self.set_font('Arial', 'B', 15)
        self.set_text_color(*COR_PRINCIPAL)
        self.cell(0, 10, 'Relatório Gerencial de Faturamento', 0, 1, 'C')
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
    print("Iniciando geração do relatório de faturamento...")
    df = get_data_from_mongo()
    if df is None: return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    hoje = datetime.now(FUSO_HORARIO)
    inicio_mes_atual = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fim_mes_anterior = inicio_mes_atual - relativedelta(microseconds=1)
    inicio_mes_anterior = fim_mes_anterior.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_ano_atual = hoje.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    df_mes_atual = df[df['emissao'] >= inicio_mes_atual]
    df_mes_anterior = df[(df['emissao'] >= inicio_mes_anterior) & (df['emissao'] < inicio_mes_atual)]
    df_ano_atual = df[df['emissao'] >= inicio_ano_atual]

    pdf = PDF('P', 'mm', 'A4')
    pdf.alias_nb_pages()
    
    # --- PÁGINA 1: DASHBOARD PRINCIPAL ---
    # (Sem alterações)
    pdf.add_page()
    pdf.create_title('Dashboard de Faturamento')
    kpi_mes_atual = df_mes_atual['valor_total_nota'].sum()
    kpi_mes_anterior = df_mes_anterior['valor_total_nota'].sum()
    kpi_ano_atual = df_ano_atual['valor_total_nota'].sum()
    pdf.create_kpi_box('Faturamento Mês Atual', kpi_mes_atual, x=10, y=45)
    pdf.create_kpi_box('Faturamento Mês Anterior', kpi_mes_anterior, x=78, y=45)
    pdf.create_kpi_box('Acumulado Ano', kpi_ano_atual, x=146, y=45)
    pdf.ln(30)
    print("Gerando gráficos da página 1...")
    faturamento_filial_mes_atual = df_mes_atual.groupby('filial_nome')['valor_total_nota'].sum()
    create_bar_chart(faturamento_filial_mes_atual, 'Faturamento por Filial (Mês Atual)', 'chart_p1_1.png')
    pdf.image('chart_p1_1.png', x=10, w=190)
    faturamento_filial_mes_anterior = df_mes_anterior.groupby('filial_nome')['valor_total_nota'].sum()
    create_bar_chart(faturamento_filial_mes_anterior, 'Faturamento por Filial (Mês Anterior)', 'chart_p1_2.png')
    pdf.image('chart_p1_2.png', x=10, w=190)
    faturamento_filial_ano = df_ano_atual.groupby('filial_nome')['valor_total_nota'].sum()
    create_bar_chart(faturamento_filial_ano, 'Faturamento por Filial (Acumulado Ano)', 'chart_p1_3.png')
    pdf.image('chart_p1_3.png', x=10, w=190)

    # --- PÁGINA 2: DETALHAMENTO ---
    # (Sem alterações)
    pdf.add_page()
    pdf.create_title('Detalhamento - Últimas Notas Fiscais')
    for filial in FILIAIS_ORDEM:
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(*COR_SECUNDARIA)
        pdf.cell(0, 10, filial, 0, 1)
        df_filial = df[df['filial_nome'] == filial].nlargest(10, 'emissao')
        if df_filial.empty:
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 10, 'Nenhuma nota fiscal encontrada para esta filial.', 0, 1)
        else:
            headers = ['Emissão', 'Nota Fiscal', 'Cliente', 'Valor Total']
            column_widths = [25, 25, 90, 30]
            table_data = []
            for _, row in df_filial.iterrows():
                table_data.append([row['emissao'].strftime('%d/%m/%Y'), row['numero_nota'], str(row['EMPRESA'])[:50], f"R$ {row['valor_total_nota']:,.2f}"])
            pdf.create_styled_table(headers, table_data, column_widths)
        pdf.ln(5)

    # --- PÁGINA 3: ANÁLISE DE EVOLUÇÃO ---
    pdf.add_page()
    pdf.create_title('Análise de Evolução Mensal')
    
    fim_periodo_evolucao = inicio_mes_atual
    inicio_periodo_evolucao = fim_periodo_evolucao - relativedelta(months=12)
    df_evolucao = df[(df['emissao'] >= inicio_periodo_evolucao) & (df['emissao'] < fim_periodo_evolucao)]
    
    # --- LÓGICA DE VERIFICAÇÃO ADICIONADA ---
    # Verifica se há dados de pelo menos 2 meses distintos para desenhar uma linha
    if not df_evolucao.empty and df_evolucao['emissao'].dt.to_period('M').nunique() > 1:
        # Gráfico 1: Evolução Geral
        evolucao_geral = df_evolucao.set_index('emissao').resample('MS')['valor_total_nota'].sum()
        evolucao_geral.index = evolucao_geral.index.strftime('%b/%Y')
        print("Gerando gráfico de evolução geral...")
        create_line_chart(evolucao_geral, 'Faturamento Mensal Geral (Últimos 12 Meses)', 'chart_p3_1.png', is_multiple_lines=False)
        pdf.image('chart_p3_1.png', x=10, w=190)
        pdf.ln(5)

        # Gráfico 2: Evolução por Filial
        print("Gerando gráfico de evolução por filial...")
        evolucao_por_filial = {}
        for filial_nome in FILIAIS_ORDEM:
            df_filial_evolucao = df_evolucao[df_evolucao['filial_nome'] == filial_nome]
            if not df_filial_evolucao.empty:
                data_filial = df_filial_evolucao.set_index('emissao').resample('MS')['valor_total_nota'].sum()
                data_filial.index = data_filial.index.strftime('%b/%Y')
                evolucao_por_filial[filial_nome] = data_filial
        
        create_line_chart(evolucao_por_filial, 'Faturamento Mensal por Filial (Últimos 12 Meses)', 'chart_p3_2.png', is_multiple_lines=True)
        pdf.image('chart_p3_2.png', x=10, w=190)
    else:
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 10, 'Dados insuficientes para gerar gráficos de evolução mensal.', 0, 1)
        pdf.set_font('Arial', 'I', 8)
        pdf.cell(0, 10, '(É necessário ter dados de pelo menos dois meses completos no último ano)', 0, 1)
    
    report_filename = f"Relatorio_Faturamento_{hoje.strftime('%Y-%m-%d')}.pdf"
    full_path = os.path.join(OUTPUT_FOLDER, report_filename)
    pdf.output(full_path)
    print(f"Relatório final salvo com sucesso em: {full_path}")

    for file in os.listdir('.'):
        if file.startswith('chart_') and file.endswith('.png'):
            os.remove(file)
    print("Arquivos de imagem temporários removidos.")

if __name__ == '__main__':
    main()