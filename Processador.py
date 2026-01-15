
import pandas as pd
import pymongo
import os
import glob
import re
from datetime import datetime
import pytz

# --- CONFIGURAÇÕES ---
# Conexão com o MongoDB
MONGO_URI = "mongodb://admin:123@192.168.17.200:27017/?authSource=admin"
DB_NAME = "faturamento_db"
COLLECTION_NAME = "notas_fiscais"
FUSO_HORARIO = pytz.timezone('America/Sao_Paulo')   
# Caminhos das pastas (relativos à localização do script)
INPUT_FOLDER = 'input'
PROCESSED_FOLDER = 'processed'

# Regra de negócio para fusão de filiais
MAPA_FILIAIS = {
    'SS': {'codigo': 'JF', 'nome': 'Juiz de Fora'},
    'SZM': {'codigo': 'JF', 'nome': 'Juiz de Fora'},
    'JF': {'codigo': 'JF', 'nome': 'Juiz de Fora'},
    'VA': {'codigo': 'VA', 'nome': 'Vale Aço'},
    'RJ': {'codigo': 'RJ', 'nome': 'Rio de Janeiro'},
}

# --- FUNÇÕES ---

def get_db_connection(uri, db_name):
    """Estabelece a conexão com o MongoDB e retorna o objeto do banco."""
    try:
        client = pymongo.MongoClient(uri)
        client.admin.command('ping')  # Verifica se a conexão foi bem-sucedida
        print("Conexão com MongoDB estabelecida com sucesso.")
        return client[db_name]
    except pymongo.errors.ConnectionFailure as e:
        print(f"Não foi possível conectar ao MongoDB: {e}")
        return None

def extract_filial_code(filename):
    """Extrai o código da filial do nome do arquivo (ex: faturamento_JF_2025.xlsx -> JF)."""
    # Procura por códigos conhecidos no nome do arquivo, ignorando maiúsculas/minúsculas
    match = re.search(r'(SS|SZM|JF|VA|RJ)', filename, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    print(f"Aviso: Não foi possível extrair o código da filial do arquivo '{filename}'.")
    return None

def process_file(filepath, db):
    """Lê um arquivo Excel, transforma os dados e os carrega no MongoDB."""
    filename = os.path.basename(filepath)
    print(f"\n--- Processando arquivo: {filename} ---")

    filial_original = extract_filial_code(filename)
    if not filial_original:
        return

    try:
        df = pd.read_excel(filepath, engine='openpyxl')
        
        # --- FASE DE TRANSFORMAÇÃO ---
        
        df.rename(columns={
            'Numero da nota': 'numero_nota',
            'empresa': 'EMPRESA', # Ajustado para o nome que usamos no relatório
            'Pedido do Cliente': 'pedido_cliente',
            'Numero PV': 'numero_pv',
            'vendedor': 'vendedor',
            'Emissão': 'emissao',
            'CFOP': 'cfop',
            'Total': 'valor_total_nota'
        }, inplace=True)

        # --- LINHA CORRIGIDA AQUI ---
        # Converte a coluna para datetime e imediatamente aplica o fuso horário correto.
        df['emissao'] = pd.to_datetime(df['emissao']).dt.tz_localize(FUSO_HORARIO)
        
        filial_mapeada = MAPA_FILIAIS.get(filial_original, {})
        df['filial_codigo'] = filial_mapeada.get('codigo', filial_original)
        df['filial_nome'] = filial_mapeada.get('nome', 'Desconhecida')

        df['_id'] = df['numero_nota'].astype(str) + '_' + df['filial_codigo']
        
        df['data_carga'] = datetime.now()

        data_to_load = df.to_dict('records')
        
        # --- FASE DE CARREGAMENTO ---
        
        if not data_to_load:
            print("Nenhum dado para carregar.")
            return

        collection = db[COLLECTION_NAME]
        updates = 0
        inserts = 0

        for record in data_to_load:
            result = collection.update_one(
                {'_id': record['_id']},
                {'$set': record},
                upsert=True
            )
            if result.upserted_id is not None:
                inserts += 1
            elif result.matched_count > 0:
                updates += 1
        
        print(f"Carregamento concluído: {inserts} novas notas inseridas, {updates} notas atualizadas.")

    except Exception as e:
        print(f"Ocorreu um erro ao processar o arquivo {filename}: {e}")


def main():
    """Função principal que orquestra todo o processo de ETL."""
    db = get_db_connection(MONGO_URI, DB_NAME)
    
    # --- CORREÇÃO AQUI ---
    # Nós só queremos parar o script se a conexão FALHAR (ou seja, se db for None).
    if db is None:
        print("Encerrando o script devido à falha na conexão com o banco de dados.")
        return

    # Cria a pasta de arquivos processados se ela não existir
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)

    # Busca por todos os arquivos .xlsx na pasta de entrada
    files_to_process = glob.glob(os.path.join(INPUT_FOLDER, '*.xlsx'))

    if not files_to_process:
        print("Nenhum arquivo Excel encontrado na pasta 'input'.")
        return

    for filepath in files_to_process:
        process_file(filepath, db)
        # Move o arquivo processado para a pasta 'processed'
        try:
            filename = os.path.basename(filepath)
            os.rename(filepath, os.path.join(PROCESSED_FOLDER, filename))
            print(f"Arquivo '{filename}' movido para a pasta '{PROCESSED_FOLDER}'.")
        except Exception as e:
            print(f"Erro ao mover o arquivo {filename}: {e}")

if __name__ == "__main__":
    main()