import os, certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
import requests, gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

DATAJUD_API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
TELEGRAM_TOKEN = "8271848621:AAENND-D14IFmv08_gcubOhnUJFXyfcTXWQ"
TELEGRAM_CHAT_ID = "7672434825"
SHEET_NAME = "gestao processual"
CREDENTIALS_FILE = "credenciais_google.json"

def conectar_sheets():
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
    gc = gspread.authorize(creds)
    return gc.open(SHEET_NAME).sheet1

TRIBUNAIS_VALIDOS = {"tjgo": "tjgo", "tjdft": "tjdft", "trt10": "trt10", "trt-10": "trt10"}

def consultar_datajud(numero_processo, tribunal):
    tribunal_api = TRIBUNAIS_VALIDOS.get(tribunal.lower().strip())
    if not tribunal_api:
        print(f"  Tribunal {tribunal} nao suportado")
        return None
    url = f"https://api-publica.datajud.cnj.jus.br/api_publica_{tribunal}/_search"
    headers = {"Authorization": f"APIKey {DATAJUD_API_KEY}", "Content-Type": "application/json"}
    query = {"query": {"match": {"numeroProcesso": numero_processo}}}
    try:
        resp = requests.post(url, headers=headers, json=query, timeout=15)
        hits = resp.json().get("hits", {}).get("hits", [])
        if not hits:
            return None
        movimentos = hits[0]["_source"].get("movimentos", [])
        if not movimentos:
            return None
        ultimo = sorted(movimentos, key=lambda x: x.get("dataHora",""), reverse=True)[0]
        return {"nome": ultimo.get("nome","Sem descricao"), "data": ultimo.get("dataHora","")[:10]}
    except Exception as e:
        print(f"  Erro: {e}")
        return None


def criar_evento_calendar(titulo, descricao, data_str):
    try:
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials as C2
        sc = ['https://www.googleapis.com/auth/calendar']
        cr = C2.from_service_account_file(CREDENTIALS_FILE, scopes=sc)
        srv = build('calendar', 'v3', credentials=cr)
        ev = {
            'summary': titulo,
            'description': descricao,
            'start': {'date': data_str, 'timeZone': 'America/Sao_Paulo'},
            'end': {'date': data_str, 'timeZone': 'America/Sao_Paulo'},
            'reminders': {'useDefault': False, 'overrides': [
                {'method': 'email', 'minutes': 1440},
                {'method': 'popup', 'minutes': 60}
            ]}
        }
        srv.events().insert(calendarId='primary', body=ev).execute()
        print('  Evento criado no Calendar!')
    except Exception as e:
        print('  Erro Calendar:', e)

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}, timeout=10)
        print("  Telegram enviado!")
    except Exception as e:
        print(f"  Erro Telegram: {e}")

def verificar_processos():
    print(f"\n{'='*50}")
    print(f"Verificando - {datetime.now():%d/%m/%Y %H:%M}")
    sheet = conectar_sheets()
    registros = sheet.get_all_records()
    novidades = 0
    for i, row in enumerate(registros, start=2):
        num = row.get("numero_processo","").strip()
        tribunal = row.get("tribunal","").strip().lower()
        ultima = row.get("ultima_movimentacao","").strip()
        cliente = row.get("cliente","desconhecido").strip()
        if not num or not tribunal:
            continue
        print(f"-> {num} [{tribunal.upper()}]")
        resultado = consultar_datajud(num, tribunal)
        if not resultado:
            continue
        if resultado["nome"] != ultima:
            novidades += 1
            sheet.update_cell(i, 4, resultado["nome"])
            sheet.update_cell(i, 5, resultado["data"])
            msg = (f"NOVA MOVIMENTACAO\n"
                   f"Processo: {num}\n"
                   f"Cliente: {cliente}\n"
                   f"Tribunal: {tribunal.upper()}\n"
                   f"Movimento: {resultado['nome']}\n"
                   f"Data: {resultado['data']}")
            enviar_telegram(msg)
    print(f"Concluido. {novidades} novidade(s).")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    verificar_processos()
