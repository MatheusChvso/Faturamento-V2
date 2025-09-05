import pymongo
import pytz
from datetime import datetime

# --- CONFIGURAÇÕES ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "faturamento_db"
COLLECTION_NAME = "notas_fiscais"

# --- MÊS E ANO PARA DEPURAR ---
ANO = 2025
MES = 8

# --- CÓDIGO DE DEPURACAO ---

def main():
    """
    Conecta ao MongoDB, busca todas as notas fiscais do mês/ano especificado
    e imprime um relatório detalhado no terminal.
    """
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print("Conexão com MongoDB estabelecida com sucesso.")
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {e}")
        return

    # Define o fuso horário para garantir que a consulta seja precisa
    fuso_horario = pytz.timezone('America/Sao_Paulo')

    # Define o início e o fim do mês que queremos analisar
    # Início: primeiro dia do mês, à meia-noite
    # Fim: primeiro dia do mês SEGUINTE, à meia-noite
    start_date = fuso_horario.localize(datetime(ANO, MES, 1, 0, 0, 0))
    
    if MES == 12:
        end_date = fuso_horario.localize(datetime(ANO + 1, 1, 1, 0, 0, 0))
    else:
        end_date = fuso_horario.localize(datetime(ANO, MES + 1, 1, 0, 0, 0))

    print("-" * 60)
    print(f"Buscando notas fiscais com data de emissão entre:")
    print(f"Início: {start_date.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    print(f"Fim (não incluso): {end_date.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    print("-" * 60)

    # Cria a consulta (query) para o MongoDB
    query = {
        "emissao": {
            "$gte": start_date,
            "$lt": end_date
        }
    }

    # Executa a busca e ordena os resultados por data de emissão
    notas_de_agosto = list(collection.find(query).sort("emissao", 1))

    if not notas_de_agosto:
        print("\nNenhuma nota fiscal encontrada para Agosto de 2025.")
        return

    total_faturado = 0
    
    # Imprime o cabeçalho do relatório
    print("\n{:<15} | {:<25} | {:<10} | {:>15}".format(
        "Nº NOTA", "DATA EMISSÃO (LOCAL)", "FILIAL", "VALOR (R$)"))
    print("-" * 70)

    # Itera sobre cada nota encontrada e a imprime no terminal
    for nota in notas_de_agosto:
        # Pega a data e a converte para o fuso local para exibição
        data_emissao_local = nota['emissao'].astimezone(fuso_horario)
        
        print("{:<15} | {:<25} | {:<10} | {:>15,.2f}".format(
            nota.get('numero_nota', 'N/A'),
            data_emissao_local.strftime('%d/%m/%Y %H:%M:%S'),
            nota.get('filial_codigo', 'N/A'),
            nota.get('valor_total_nota', 0)
        ))
        total_faturado += nota.get('valor_total_nota', 0)

    print("-" * 70)
    print(f"TOTAL DE NOTAS ENCONTRADAS: {len(notas_de_agosto)}")
    print(f"SOMA TOTAL PARA O PERÍODO: R$ {total_faturado:,.2f}")
    print("-" * 70)

    client.close()

if __name__ == "__main__":
    main()