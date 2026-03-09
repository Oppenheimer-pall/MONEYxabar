# 💳 CARD BOT

> Professional Telegram karta boshqaruv va to'lov boti

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)
![Python](https://img.shields.io/badge/python-3.11-blue)

---

## 🌟 Imkoniyatlar

| Funksiya | Tavsif |
|----------|--------|
| 💳 Karta qo'shish | Visa, Mastercard, Humo, Uzcard — Luhn tekshiruvi |
| 💸 Pul o'tkazish | Balans tekshiruvi + avtomatik komissiya |
| 🧾 To'lov cheki | Har bir o'tkazmada chiroyli chek |
| 📊 Hisobot | Oylik kirim/chiqim statistikasi |
| 📋 Tarix | So'nggi tranzaksiyalar |

---

## 🚀 GitHub + Railway Deploy

### 1️⃣ GitHub'ga yuklash

```bash
git init
git add .
git commit -m "🚀 Initial commit: Card Bot"
git remote add origin https://github.com/USERNAME/card-bot.git
git branch -M main
git push -u origin main
```

### 2️⃣ Railway'da deploy

1. [railway.app](https://railway.app) → **"New Project"**
2. **"Deploy from GitHub repo"** → `card-bot` tanlang
3. ✅ Avtomatik deploy boshlanadi

### 3️⃣ Environment Variables (Railway → Variables)

| Variable | Qiymat |
|----------|--------|
| `BOT_TOKEN` | `1234567890:AAF...` |
| `ADMIN_IDS` | `123456789` |
| `DB_PATH` | `/data/card_bot.db` |

### 4️⃣ Persistent Volume

Railway → **"Add Volume"** → Mount path: `/data`

> ⚠️ Volume bo'lmasa ma'lumotlar har deployda o'chadi!

### 5️⃣ GitHub Actions (Avtomatik deploy)

GitHub → Settings → Secrets:
- `RAILWAY_TOKEN` → Railway'dan olingan token
- `RAILWAY_SERVICE_NAME` → Service nomi

---

## 💻 Lokal ishga tushirish

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # .env ni to'ldiring
python bot.py
```

---

## 💸 Komissiya tizimi

| Karta | Foiz | Min | Max |
|-------|------|-----|-----|
| Humo / Uzcard | 0.3% | 300 so'm | 3,000 so'm |
| Visa / Mastercard | 0.5% | 500 so'm | 5,000 so'm |

---

## 📁 Fayl tuzilmasi

```
card_bot/
├── .github/workflows/deploy.yml  ← CI/CD
├── bot.py                        ← Asosiy bot
├── database.py                   ← SQLite
├── card_utils.py                 ← Karta utils
├── config.py                     ← Env sozlamalar
├── requirements.txt
├── Dockerfile
├── railway.toml
├── .env.example
└── .gitignore
```

---

## 🔒 Xavfsizlik

- ❌ `.env` faylini GitHub'ga push qilmang
- ✅ Faqat Railway Variables orqali token kiriting
