# Crypto Signal Analyzer (Binance WebSocket → FastAPI → Telegram)

مشروع ويب متكامل لتحليل إشارات التداول اللحظية للعملات المشفرة باستخدام بيانات WebSocket من Binance، وإرسال الإشارات إلى بوت Telegram.

## بنية المشروع
```
crypto-signal-analyzer/
├─ frontend/
│  ├─ index.html
│  └─ script.js
├─ backend/
│  ├─ main.py
│  └─ requirements.txt
└─ README.md
```

## المتطلبات
- Python 3.10+
- Node/browser for the frontend (modern browser)
- حساب بوت Telegram (BOT_TOKEN) و CHAT_ID الهدف

## الإعداد والتشغيل محلياً (Backend)
1. انتقل إلى مجلد `backend/`.
2. إنشاء بيئة افتراضية (موصى به):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # على لينكس/ماك
   .venv\\Scripts\\activate   # على ويندوز
   ```
3. تثبيت المتطلبات:
   ```bash
   pip install -r requirements.txt
   ```
4. تعديل القيم في `backend/main.py` أعلى الملف (`BOT_TOKEN` و `CHAT_ID`) بالقيم الخاصة بك.
5. تشغيل الخادم:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

## الإعداد والتشغيل (Frontend)
- افتح `frontend/index.html` في متصفحك مباشرة أو استضفه من خادم ثابت.
- في الحقل "رمز العملة" اكتب مثلاً `DOGEUSDT` ثم اضغط "ابدأ التحليل".
- الواجهة ستتصل مباشرة بـ WebSocket الخاص بـ Binance لجلب بيانات الشمعة 1 دقيقة وترسل بيانات الإغلاق إلى الخادم الخلفي للمعالجة.

## النشر
- يمكنك نشر الـ backend على Render، Heroku، أو Vercel (Serverless) أو Replit.
- تأكد من ضبط المتغيرات BOT_TOKEN و CHAT_ID كمتغيرات بيئة عند النشر (أو تعديل الملف مباشرة قبل النشر).

## ملاحظات تقنية
- تم استخدام Pandas لحساب المؤشرات الفنية (RSI, MACD, EMA, Bollinger Bands).
- تم إعداد CORS في FastAPI للسماح للواجهة الأمامية بالاتصال.
- يتعامل الخادم والعميل مع حالات الخطأ (WebSocket مقطوع، فشل اتصال Telegram، ونقص البيانات) مع تسجيل وتحذير.
- هذا مشروع تعليمي ويجب اختبار الإشارات جيداً قبل الاستخدام الحقيقي في التداول.

