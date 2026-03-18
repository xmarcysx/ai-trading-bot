# AI Crypto Trader Dashboard

Aplikacja składa się z dwóch części:

- `frontend/` - dashboard w Next.js (React + TypeScript + lightweight-charts).
- `bot/` - backend FastAPI z pętlą alertów (Bybit przez `ccxt`) i wysyłką powiadomień na Telegram.

Dashboard pokazuje cenę, metryki i sygnały, a bot cyklicznie analizuje świece oraz generuje alerty według aktywnych strategii.

## Funkcje

- Obsługa wielu strategii jednocześnie:
	- `ema_cross_9_18`
	- `macd_cross`
	- `market_structure_85_15`
- Obsługa wielu par (`ETH/USDT`, `BTC/USDT`).
- Interaktywny wykres świecowy z EMA 9/18 i panelem oscylatora (MSO + MACD + histogram).
- Konfiguracja alertów z UI (`/api/config`) i szybkie włączanie/wyłączanie strategii (`/api/strategies/active`).
- Powiadomienia Telegram po wykryciu sygnału.

## Architektura

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Frontend pobiera dane z backendu przez:
	- `GET /api/state`
	- `GET /api/config`
	- `POST /api/config`
	- `POST /api/strategies/active`
	- `GET /api/chart?symbol=ETH%2FUSDT&timeframe=1h`

## Wymagania

- Node.js 20+
- npm 10+
- Python 3.10+

## Szybki start (lokalnie)

Uruchom backend i frontend w osobnych terminalach.
Poniższe komendy zakładają, że startujesz z katalogu głównego projektu (`Playground`).

### 1) Backend (FastAPI + bot)

```powershell
cd bot

# Jeżeli nie masz jeszcze środowiska:
python -m venv venv

# Aktywacja (Windows PowerShell)
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
python main.py
```

Po starcie backend działa na `http://localhost:8000`.

### 2) Frontend (Next.js)

```powershell
cd frontend
npm install
npm run dev
```

Następnie otwórz `http://localhost:3000`.

## Konfiguracja alertów

Konfigurację możesz zmieniać na dwa sposoby:

- z poziomu dashboardu (rekomendowane),
- przez plik `../bot/bot_config.json`.

Najważniejsze pola:

- `telegram_token`
- `telegram_chat_id`
- `active_strategies`
- `active_symbols`
- `timeframe` (`1m`, `5m`, `15m`, `1h`, `4h`)
- `repeat_alerts`
- `strategies_active`

Przykład:

```json
{
	"telegram_token": "<TELEGRAM_BOT_TOKEN>",
	"telegram_chat_id": "<TELEGRAM_CHAT_ID>",
	"active_strategies": ["ema_cross_9_18", "macd_cross"],
	"active_symbols": ["ETH/USDT", "BTC/USDT"],
	"timeframe": "1h",
	"repeat_alerts": false,
	"strategies_active": true
}
```

## Skrypty frontendu

- `npm run dev` - tryb developerski
- `npm run build` - build produkcyjny
- `npm run start` - start po buildzie
- `npm run lint` - lint

## Uwagi bezpieczeństwa

- Nie commituj prawdziwych tokenów Telegram do repozytorium.
- Traktuj `bot_config.json` jako dane lokalne (sekrety i ustawienia środowiskowe).

## Najczęstsze problemy

- Brak danych w dashboardzie: sprawdź, czy backend działa na porcie `8000`.
- Błędy przy pobieraniu świec: sprawdź połączenie sieciowe i dostępność API giełdy.
- Brak alertów na Telegramie: zweryfikuj `telegram_token`, `telegram_chat_id` i `strategies_active`.
