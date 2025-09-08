import pymongo
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz

# --- CONFIGURAÇÕES ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "faturamento_db"
COLLECTION_NAME = "notas_fiscais"
FUSO_HORARIO = pytz.timezone('America/Sao_Paulo')

def main():
    print("--- Verificador de Dados para Gráficos de Evolução ---")
    
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        df = pd.DataFrame(list(db[COLLECTION_NAME].find()))
        client.close()
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {e}")
        return

    if df.empty:
        print("O banco de dados está vazio. Nenhum dado para analisar.")
        return

    s_emissao = pd.to_datetime(df['emissao'])
        
        # Força todas as datas a terem o fuso UTC e depois converte para o fuso local
        # Isso padroniza tanto as datas 'naive' (sem fuso) quanto as 'aware' (com fuso)
    df['emissao'] = s_emissao.dt.tz_localize('UTC', ambiguous='infer').dt.tz_convert(FUSO_HORARIO)

    # --- Lógica exata usada no script do relatório ---
    hoje = datetime.now(FUSO_HORARIO)
    inicio_mes_atual = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    fim_periodo_evolucao = inicio_mes_atual
    inicio_periodo_evolucao = fim_periodo_evolucao - relativedelta(months=12)

    df_evolucao = df[(df['emissao'] >= inicio_periodo_evolucao) & (df['emissao'] < fim_periodo_evolucao)]

    print(f"\nAnalisando o período de: {inicio_periodo_evolucao.strftime('%d/%m/%Y')} até {fim_periodo_evolucao.strftime('%d/%m/%Y')}")

    if df_evolucao.empty:
        print("Nenhum dado de faturamento encontrado neste período.")
        return

    # Conta quantos meses únicos existem nos dados filtrados
    meses_unicos = df_evolucao['emissao'].dt.to_period('M').unique()
    num_meses_unicos = len(meses_unicos)

    print(f"\nMeses completos encontrados no período: {[str(m) for m in sorted(meses_unicos)]}")
    print(f"Total de meses únicos encontrados: {num_meses_unicos}")
    print("-" * 55)

    if num_meses_unicos > 1:
        print("✅ Resultado: Os gráficos de evolução DEVERIAM ser gerados.")
    else:
        print("❌ Resultado: Os gráficos de evolução NÃO serão gerados.")
        print("   Motivo: É necessário ter dados de pelo menos 2 meses completos diferentes.")

if __name__ == "__main__":
    main()