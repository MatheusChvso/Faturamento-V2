import pymongo
import pandas as pd
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz # Para lidar com fusos horários

# --- CONFIGURAÇÕES GLOBAIS ---

# Conexão com o MongoDB
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "faturamento_db"
COLLECTION_NAME = "notas_fiscais"

# Configurações do Relatório
OUTPUT_FOLDER = 'output'
FILIAIS_ORDEM = ["Juiz de Fora", "Vale Aço", "Rio de Janeiro"]
FUSO_HORARIO = pytz.timezone('America/Sao_Paulo')

# Paleta de Cores (consistente com o projeto de Vendas)
COR_PRINCIPAL = "#003f5c"
COR_SECUNDARIA = "#2f4f4f"
CORES_GRAFICOS = ["#003f5c", "#ff6361", "#ffa600"]

# --- CONEXÃO E CONSULTAS AO BANCO DE DADOS ---

def get_data_from_mongo():
    """Busca todos os dados da coleção e retorna como um DataFrame do Pandas."""
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Converte a coleção inteira para uma lista e depois para DataFrame
        df = pd.DataFrame(list(collection.find()))
        
        if df.empty:
            print("A coleção no MongoDB está vazia. Nenhum dado para processar.")
            return None

        # Garante que a coluna de emissão é do tipo datetime e ajusta para o fuso horário correto
        df['emissao'] = pd.to_datetime(df['emissao']).dt.tz_localize('UTC').dt.tz_convert(FUSO_HORARIO)
        client.close()
        return df
    except Exception as e:
        print(f"Erro ao conectar ou buscar dados no MongoDB: {e}")
        return None

# --- FUNÇÕES DE GERAÇÃO DE GRÁFICOS ---

def create_bar_chart(data, title, filename):
    """Cria um gráfico de barras horizontais e o salva como imagem."""
    if data.empty or data.sum() == 0:
        # Cria um gráfico vazio se não houver dados
        fig, ax = plt.subplots(figsize=(10, 2))
        ax.text(0.5, 0.5, 'Sem dados para o período', horizontalalignment='center', verticalalignment='center')
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        data = data.reindex(FILIAIS_ORDEM, fill_value=0)
        fig, ax = plt.subplots(figsize=(10, 2))
        bars = ax.barh(data.index, data.values, color=CORES_GRAFICOS)
        ax.set_xlabel('Valor Faturado (R$)')
        ax.set_title(title, loc='left', color=COR_SECUNDARIA)
        ax.xaxis.set_major_formatter(mticker.StrMethodFormatter('R$ {x:,.2f}'))
        # Garante que o eixo comece em zero
        ax.set_xlim(left=0)
        # Remove bordas desnecessárias
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        # Adiciona rótulos de dados
        for bar in bars:
            width = bar.get_width()
            if width > 0:
                ax.text(width * 1.01, bar.get_y() + bar.get_height()/2, f'R$ {width:,.2f}', va='center')

    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

def create_line_chart(data, title, filename):
    """Cria um gráfico de linhas e o salva como imagem."""
    fig, ax = plt.subplots(figsize=(10, 4))
    if data.empty:
        ax.text(0.5, 0.5, 'Dados insuficientes para gerar evolução', ha='center', va='center')
    else:
        ax.plot(data.index, data.values, marker='o', color=COR_PRINCIPAL)
        ax.set_title(title, loc='left', color=COR_SECUNDARIA)
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
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Relatório Gerencial de Faturamento', 0, 1, 'C')
        self.set_font('Arial', '', 8)
        self.cell(0, 5, f'Gerado em: {datetime.now(FUSO_HORARIO).strftime("%d/%m/%Y %H:%M:%S")}', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', 0, 0, 'C')

    def create_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(5)

    def create_kpi_box(self, title, value, x, y):
        self.set_xy(x, y)
        self.set_font('Arial', 'B', 10)
        self.set_fill_color(240, 240, 240)
        self.cell(65, 10, title, 1, 0, 'C', fill=True)
        self.set_xy(x, y + 10)
        self.set_font('Arial', '', 12)
        self.set_fill_color(255, 255, 255)
        formatted_value = f'R$ {value:,.2f}' if isinstance(value, (int, float)) else str(value)
        self.cell(65, 15, formatted_value, 1, 1, 'C')

# --- FUNÇÃO PRINCIPAL ---

def main():
    print("Iniciando geração do relatório de faturamento...")
    
    df = get_data_from_mongo()
    if df is None:
        print("Finalizando script pois não há dados para processar.")
        return

    # Garante que a pasta de output exista
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    # Define os períodos de tempo com base na data atual e fuso horário
    hoje = datetime.now(FUSO_HORARIO)
    inicio_mes_atual = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fim_mes_anterior = inicio_mes_atual - relativedelta(microseconds=1)
    inicio_mes_anterior = fim_mes_anterior.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_ano_atual = hoje.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Filtros de dados
    df_mes_atual = df[df['emissao'] >= inicio_mes_atual]
    df_mes_anterior = df[(df['emissao'] >= inicio_mes_anterior) & (df['emissao'] < inicio_mes_atual)]
    df_ano_atual = df[df['emissao'] >= inicio_ano_atual]

    # --- Inicia a criação do PDF ---
    pdf = PDF('P', 'mm', 'A4')
    pdf.alias_nb_pages()
    
    # --- PÁGINA 1: DASHBOARD PRINCIPAL ---
    pdf.add_page()
    pdf.create_title('Dashboard de Faturamento')

    # Calcula KPIs
    kpi_mes_atual = df_mes_atual['valor_total_nota'].sum()
    kpi_mes_anterior = df_mes_anterior['valor_total_nota'].sum()
    kpi_ano_atual = df_ano_atual['valor_total_nota'].sum()

    # Desenha caixas de KPI
    pdf.create_kpi_box('Faturamento Mês Atual', kpi_mes_atual, x=10, y=35)
    pdf.create_kpi_box('Faturamento Mês Anterior', kpi_mes_anterior, x=78, y=35)
    pdf.create_kpi_box('Faturamento Acumulado Ano', kpi_ano_atual, x=146, y=35)
    pdf.ln(30)
    
    # Gera e insere gráficos de barras
    print("Gerando gráficos da página 1...")
    
    faturamento_filial_mes_atual = df_mes_atual.groupby('filial_nome')['valor_total_nota'].sum()
    create_bar_chart(faturamento_filial_mes_atual, 'Faturamento por Filial (Mês Atual)', 'chart_p1_1.png')
    pdf.image('chart_p1_1.png', x=10, w=190)
    pdf.ln(5)

    faturamento_filial_mes_anterior = df_mes_anterior.groupby('filial_nome')['valor_total_nota'].sum()
    create_bar_chart(faturamento_filial_mes_anterior, 'Faturamento por Filial (Mês Anterior)', 'chart_p1_2.png')
    pdf.image('chart_p1_2.png', x=10, w=190)
    pdf.ln(5)
    
    faturamento_filial_ano = df_ano_atual.groupby('filial_nome')['valor_total_nota'].sum()
    create_bar_chart(faturamento_filial_ano, 'Faturamento por Filial (Acumulado Ano)', 'chart_p1_3.png')
    pdf.image('chart_p1_3.png', x=10, w=190)

    # --- PÁGINA 2: DETALHAMENTO ---
    pdf.add_page()
    pdf.create_title('Detalhamento - Últimas Notas Fiscais')

    for filial in FILIAIS_ORDEM:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, filial, 0, 1)
        
        df_filial = df[df['filial_nome'] == filial].nlargest(10, 'emissao')
        
        if df_filial.empty:
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 10, 'Nenhuma nota fiscal encontrada para esta filial no período.', 0, 1)
        else:
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(25, 8, 'Emissão', 1)
            pdf.cell(25, 8, 'Nota Fiscal', 1)
            pdf.cell(90, 8, 'Cliente', 1)
            pdf.cell(30, 8, 'Valor Total', 1, 1)

            pdf.set_font('Arial', '', 8)
            for _, row in df_filial.iterrows():
                pdf.cell(25, 7, row['emissao'].strftime('%d/%m/%Y'), 1)
                pdf.cell(25, 7, str(row['numero_nota']), 1)
                pdf.cell(90, 7, str(row['EMPRESA'])[:50], 1) # Limita o nome do cliente
                pdf.cell(30, 7, f"R$ {row['valor_total_nota']:,.2f}", 1, 1)
        pdf.ln(5)

    # --- PÁGINA 3: ANÁLISE DE EVOLUÇÃO ---
    pdf.add_page()
    pdf.create_title('Análise de Evolução Mensal')
    
    # Prepara dados dos últimos 12 meses completos
    fim_periodo_evolucao = inicio_mes_atual
    inicio_periodo_evolucao = fim_periodo_evolucao - relativedelta(months=12)
    df_evolucao = df[(df['emissao'] >= inicio_periodo_evolucao) & (df['emissao'] < fim_periodo_evolucao)]
    
    if not df_evolucao.empty:
        # Gráfico 1: Evolução Geral
        evolucao_geral = df_evolucao.set_index('emissao').resample('MS')['valor_total_nota'].sum()
        evolucao_geral.index = evolucao_geral.index.strftime('%b/%Y')
        create_line_chart(evolucao_geral, 'Faturamento Mensal Geral (Últimos 12 Meses)', 'chart_p3_1.png')
        pdf.image('chart_p3_1.png', x=10, w=190)
        pdf.ln(5)
    
    # --- Salva o PDF e limpa os arquivos de imagem ---
    
    report_filename = f"Relatorio_Faturamento_{hoje.strftime('%Y-%m-%d')}.pdf"
    full_path = os.path.join(OUTPUT_FOLDER, report_filename)
    pdf.output(full_path)
    print(f"Relatório salvo com sucesso em: {full_path}")

    # Limpeza dos arquivos de imagem temporários
    for file in os.listdir('.'):
        if file.startswith('chart_') and file.endswith('.png'):
            os.remove(file)
    print("Arquivos de imagem temporários removidos.")


if __name__ == '__main__':
    main()