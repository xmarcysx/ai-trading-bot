# Szybka publikacja: frontend + backend

Ten projekt ma dwie części:
- frontend: Next.js w `frontend/`
- backend + bot loop: FastAPI w `bot/main.py`

Najprostsza ścieżka publikacji, żeby front i backend od razu gadały:
- frontend: Vercel
- backend: Railway

## 1. Przygotowanie repo

1. Wypchnij aktualny kod na GitHub.
2. Upewnij się, że backend ma plik `bot/Procfile` i że startuje komendą `python main.py`.
3. Upewnij się, że frontend czyta URL API z `NEXT_PUBLIC_API_URL`.

## 2. Deploy backendu na Railway

1. Wejdź na Railway i kliknij `New Project`.
2. Wybierz `Deploy from GitHub repo` i wskaż to repo.
3. W ustawieniach serwisu ustaw:
- Root Directory: `bot`
- Start Command: `python main.py`

4. W `Variables` dodaj:
- `TELEGRAM_BOT_TOKEN=...`
- `TELEGRAM_CHAT_ID=...`

5. Po deployu skopiuj publiczny URL backendu, np. `https://twoj-bot.up.railway.app`.

6. Sprawdź endpointy:
- `https://twoj-bot.up.railway.app/api/state`
- `https://twoj-bot.up.railway.app/api/config`

## 3. Deploy frontendu na Vercel

1. Wejdź na Vercel i kliknij `Add New Project`.
2. Importuj to repo z GitHub.
3. Ustaw `Root Directory` na `frontend`.
4. Dodaj env:
- `NEXT_PUBLIC_API_URL=https://twoj-bot.up.railway.app`

5. Kliknij deploy.

## 4. Test integracji

1. Otwórz URL frontendu z Vercel.
2. Sprawdź, czy status bota się ładuje.
3. Sprawdź wykres i odświeżanie danych.
4. Wejdź w ustawienia alertów i potwierdź, że token i chat ID są widoczne.
5. Zapisz konfigurację i sprawdź, czy backend odpowiada bez błędów.

## 5. Szybki troubleshooting

1. Front nie łączy się z API:
- sprawdź `NEXT_PUBLIC_API_URL` w Vercel
- zrób `Redeploy` po zmianie env

2. Backend nie startuje:
- sprawdź logi Railway
- potwierdź, że `Root Directory=bot`

3. Brak Telegram alertów:
- sprawdź `TELEGRAM_BOT_TOKEN` i `TELEGRAM_CHAT_ID` w Railway Variables
- potwierdź, że strategie są aktywne

## 6. Ważna uwaga o free tier

Railway free ma limit godzin miesięcznie, więc to nie jest gwarantowane pełne 24/7 przez cały miesiąc.
Jeśli chcesz realne 24/7 bez usypiania, przenieś backend na Oracle Always Free VM.
