# Universal AI Cartoon Studio — بغیر کمانڈ چلائیں

## نئے Windows کمپیوٹر پر پہلی بار
- GitHub سے پورا repository clone/download کریں؛ صرف launcher فائل نہیں۔
- `uv` package manager نصب ہونا چاہیے۔ سرکاری ہدایات: https://docs.astral.sh/uv/getting-started/installation/
- پھر project folder میں **`Setup Studio.cmd`** پر ڈبل کلک کریں۔ یہ `uv.lock` کے مطابق Python 3.13 اور runtime/test dependencies الگ `.venv-windows` میں تیار کرے گا۔ پہلی بار internet درکار ہو سکتا ہے۔
- Setup کامیاب ہونے کے بعد **`Start Studio.cmd`** پر ڈبل کلک کریں۔ معمول کے launch پر کوئی download/install نہیں ہوتا۔
- اصل database، Blender models، textures اور دوسری بڑی production files GitHub code کے ساتھ شامل نہیں؛ دوسرے کمپیوٹر پر انہیں verified backup سے الگ restore کرنا ہوگا۔ نئی جگہ پر پہلی startup خالی database بنا سکتی ہے، پرانا production data خود منتقل نہیں ہوگا۔
- Blender/Unreal اور ان کے plugins بیرونی software ہیں؛ `pyproject.toml` انہیں install نہیں کرتا۔

## شروع کریں
Windows File Explorer میں اس فائل پر ڈبل کلک کریں:

`D:\Projects\06_Studio_Systems\Universal_AI_Cartoon_Studio\Start Studio.cmd`

کسی terminal میں کمانڈ لکھنے، administrator اجازت دینے، یا ہر بار dependencies نصب کرنے کی ضرورت نہیں۔ موجودہ Windows runtime `.venv-windows` سے استعمال ہوتا ہے۔

1. ایک console window کھلے گی اور مقامی Studio server شروع ہوگا۔
2. health check کامیاب ہونے پر browser میں `http://127.0.0.1:8765/workspace` خود کھلے گا۔
3. Studio استعمال کرتے وقت console window کھلی رکھیں۔ Browser بند کرنے سے server بند نہیں ہوتا۔
4. بند کرنے کے لیے اسی console window میں **Ctrl+C** دبائیں؛ یہ کوئی کمانڈ لکھنا نہیں ہے۔
5. دوبارہ ڈبل کلک کرنے پر، اگر اسی پروجیکٹ کا healthy server پہلے چل رہا ہو، تو صرف browser کھلے گا؛ دوسرا server نہیں بنایا جائے گا۔

## Desktop سے چلانا
`Start Studio.cmd` پر right-click کر کے **Send to → Desktop (create shortcut)** استعمال کریں۔ Windows 11 میں پہلے **Show more options** کھولنا پڑ سکتا ہے۔ خود launcher کو اکیلا دوسری جگہ منتقل نہ کریں؛ اس کا project folder کے ساتھ ہونا ضروری ہے۔ Shortcut منتقل کیا جا سکتا ہے۔

## موجودہ سافٹ ویئر کیا کرتا ہے؟
- مقامی catalog: projects، assets، jobs اور approvals کی موجودہ Jinja/HTMX ویب UI۔
- SQLite persistence، versioned schema، audit، Phase 02 worker/MCP بنیاد، Phase 03-A authenticated API، imports اور backup/recovery services۔
- تمام API services کے لیے ابھی الگ polished UI موجود نہیں؛ `/api/v1` bearer token مانگتا ہے۔ Token مقامی server console میں دکھتا ہے، URL یا فائل میں نہیں لکھا جاتا۔ اسے شیئر نہ کریں۔
- یہ مکمل visual flow editor یا خودکار story-to-cartoon/video application نہیں؛ launcher نئی creative phase شروع نہیں کرتا۔
- یہ Blender، Unreal، MCP server، render worker یا paid generation خود سے شروع نہیں کرتا۔

## مسئلہ آنے پر
- console window میں دکھنے والا error بتائیں؛ مکمل screenshot میں token چھپا دیں۔
- Port 8765 کسی دوسرے program کے پاس ہو تو launcher اسے بند نہیں کرے گا۔
- `.venv-windows` غائب یا خراب ہو تو launcher واضح پیغام دے گا؛ خود کوئی installation/download نہیں کرے گا۔
- اس پروجیکٹ کی پرانی `.venv` Linux کی ہے؛ اسے محفوظ رکھا گیا ہے۔ Windows کے لیے الگ locked environment بنایا گیا ہے۔
- اس window کو internet پر expose نہ کریں۔ Binding صرف `127.0.0.1` ہے۔
