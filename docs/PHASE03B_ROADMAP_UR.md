# Phase 03-B — موجودہ foundation پر تدریجی توسیع

ماخذ: صارف کی تازہ ہدایت؛ پہلے code recovery/publication، پھر موجودہ architecture پر اگلے modules۔ یہ نئے سرے سے software لکھنے کا حکم یا تمام modules کے بن جانے کا دعویٰ نہیں۔

## پہلا gate — Existing Code Recovery
- موجودہ local implementation محفوظ رہے؛ tests، migrations، protected sources اور backup rules برقرار۔
- Public GitHub source میں local chat history، secrets، database، backups یا production binaries شامل نہ ہوں۔
- Source push، remote commit verification اور clean-checkout checks کے بعد module-specific implementation scope طے کیا جائے۔

## مطلوبہ ترتیب اور نتائج
1. **Existing Code Recovery:** موجودہ source GitHub پر، dependencies/lock/setup، migrations اور tests محفوظ؛ اسے نئے version کی بنیاد بنانا۔
2. **Agent & Skills Engine:** agent definitions، skills، versioned tool permissions، approval/audit اور موجودہ FastAPI/SQLAlchemy/jobs/MCP interfaces کے مطابق integration۔ پہلے module کا مفصل قابلِ آزمائش contract الگ طے ہوگا۔
3. **Autonomous Story Factory:** اصل کہانیاں، twists/sequels، critic اور searchable story archive؛ permanent canon، references/rights اور creative approval الگ۔
4. **Visual Story Engine:** approved story سے scenes، shots اور storyboard specifications؛ outputs کی traceability اور review۔
5. **Character & Asset Factory:** consistent identities، variants/costumes، environments، editable sources، registry، provenance اور revision safety۔
6. **Camera & Video Engine:** supported providers کے ذریعے image-to-video، last-frame chaining اور continuity؛ capabilities/version/cost اور failure recovery کی عملی verification۔
7. **Editing & Audio Engine:** editing، permitted audio/music، timeline/export presets اور QC؛ protected religious voice/depic­tion rules برقرار۔
8. **Publishing & Scheduling:** YouTube/calendar integrations؛ account permissions، rights، explicit publishing authorization اور recoverable scheduling۔ Public code upload کو video auto-publishing approval نہ سمجھیں۔
9. **Workflow Designer:** visual nodes، typed dependencies، durable jobs اور live monitoring، existing services کو replace کیے بغیر۔

## Autonomy کی حدود
- Autonomy محدود، قابلِ نگرانی اور permission-based ہوگی؛ arbitrary shell/Python/tool access خودکار طور پر کھلا نہیں ہوگا۔
- Paid generation، third-party installation، destructive actions، external publishing، protected-source edits اور نئے account scopes کے لیے متعلقہ واضح اجازت برقرار رہے گی۔
- اصل IP، project canon isolation اور مذہبی/تاریخی production constraints برقرار۔
- ہر module کے لیے UX، input/output schemas، acceptance tests، error/recovery اور approval boundaries پہلے بیان ہوں گے۔

## اس publication task کی حالت
- موجودہ foundation کا safe public source push ہو چکا ہے؛ fresh-checkout CI verification/محدود bootstrap correction اس recovery کام کا حصہ ہے۔
- Existing Code Recovery کا source/verification gate پاس: remote source update `3e0106d`، GitHub run `42894203860` SUCCESS، 56 portable tests اور 89% application coverage۔ یہ باقی modules کے بننے کی تصدیق نہیں۔
- Agent & Skills Engine یا باقی creative modules اس task میں implement نہیں کیے گئے۔
- موجودہ software status: root `PROJECT_STATUS_UR.md`؛ historical dates/evidence کو نئے scope سے overwrite نہ کریں۔
