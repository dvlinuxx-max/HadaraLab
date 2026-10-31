# سياسة الخصوصية والإشعارات — HadaraLab

آخر تحديث: 2026-10-31

## سياسة الخصوصية

يحترم برنامج HadaraLab خصوصية مستخدميه، ويعمل بالكامل على جهاز المستخدم:

1. **لا يجمع البرنامج أي بيانات شخصية**، ولا يطلب إنشاء حساب أو تسجيل دخول.
2. **لا يتصل البرنامج بالإنترنت**، ولا يرسل أي بيانات أو إحصاءات استخدام أو تقارير أعطال إلى أي جهة.
3. **الملفات التي ينشئها المستخدم** (النصوص البرمجية `.m` وصور الرسوم البيانية) تُحفظ على جهازه فقط، في المكان الذي يختاره بنفسه. والمجلد الافتراضي هو `Documents\HadaraLab`.
4. **الإعدادات**: يحفظ البرنامج إعدادين فقط هما المظهر المختار (فاتح أو داكن) وحجم خط المحرر، ويُخزَّنان محلياً في سجل نظام Windows ضمن المفتاح `HKEY_CURRENT_USER\Software\Hadara\HadaraLab`.
5. **النسخ الاحتياطية للنصوص غير المحفوظة**: ينسخ البرنامج كل بضع ثوانٍ النصوص البرمجية التي لم تُحفظ بعد إلى المجلد `%LOCALAPPDATA%\HadaraLab\recovery` على جهاز المستخدم فقط، لاستعادتها إذا أُغلق البرنامج فجأة أو انقطع التيار الكهربائي. وتُحذف هذه النسخ تلقائياً عند إغلاق البرنامج بصورة طبيعية.
6. **فتح ملفات `.m`**: إذا فعّل المستخدم الخيار «فتح ملفات .m بالبرنامج» من قائمة الإعدادات، يُضاف البرنامج إلى قائمة «فتح باستخدام» لملفات `.m` ضمن المفتاح `HKEY_CURRENT_USER\Software\Classes`، ويُزال ذلك بإلغاء الخيار نفسه.
7. **الروابط الخارجية**: لا يُفتح الموقع الإلكتروني أو البريد الإلكتروني الواردان في نافذة «حول البرنامج» إلا إذا نقر المستخدم عليهما بنفسه، وعندها يتولى المتصفح أو برنامج البريد على جهاز المستخدم معالجتهما وفق سياسات الخصوصية الخاصة بهما.
8. **حذف البيانات**: يكفي لحذف كل ما يتعلق بالبرنامج حذفُ مجلد البرنامج، والمجلد `Documents\HadaraLab`، والمجلد `%LOCALAPPDATA%\HadaraLab`، ومفتاح السجل المذكور أعلاه.

## حقوق تصميم الأيقونة والهوية البصرية

- صمَّم أيقونة البرنامج وهويته البصرية (الشعار والألوان) **أحمد البصري** ([@dcssi_](https://www.instagram.com/dcssi_/)).
- حقوق التصميم محفوظة للمصمم، ويُستخدم التصميم في هذا البرنامج بإذنه.
- **لا تشمل رخصة MIT** الخاصة بالشيفرة المصدرية الأيقونةَ ولا الشعار.
- لا يجوز استخدام الأيقونة أو الشعار خارج هذا المشروع إلا بإذن مسبق من المصمم.

## التواصل

- برمجة وإعداد: محمد عبدالرحمن محمود — https://www.instagram.com/devlopxx/
- تصميم الأيقونة والهوية البصرية: أحمد البصري — https://www.instagram.com/dcssi_/
- الموقع الإلكتروني: https://mohmadev.com/
- البريد الإلكتروني للدعم: support@mohmadev.com

---

# Privacy Policy and Notices — HadaraLab

Last updated: 2026-10-31

## Privacy policy

HadaraLab runs entirely on the user's computer:

1. **No personal data is collected.** No account or sign-in is required.
2. **The program does not connect to the internet.** It sends no data, usage statistics or crash reports to anyone.
3. **Files you create** (`.m` scripts and saved figures) stay on your computer, in the location you choose. The default folder is `Documents\HadaraLab`.
4. **Settings:** only the chosen theme (light or dark) and the editor font size are stored, locally in the Windows registry under `HKEY_CURRENT_USER\Software\Hadara\HadaraLab`.
5. **Backup copies of unsaved scripts:** every few seconds, scripts with unsaved changes are copied to `%LOCALAPPDATA%\HadaraLab\recovery` on your computer only, so they can be restored after a crash or power cut. These copies are deleted automatically when HadaraLab closes normally.
6. **Opening `.m` files:** if you turn on "Open .m Files with HadaraLab" in the Settings menu, HadaraLab is added to the "Open with" list of `.m` files under `HKEY_CURRENT_USER\Software\Classes`. Turning the option off removes it.
7. **External links:** the website and e-mail address in the About window open only when you click them, in your own browser or mail program, under their own privacy policies.
8. **Removing all data:** delete the program folder, the `Documents\HadaraLab` folder, the `%LOCALAPPDATA%\HadaraLab` folder and the registry key above.

## Icon and visual identity

- The app icon and visual identity (logo and colors) were designed by **Ahmed Al Basri** ([instagram.com/dcssi_](https://www.instagram.com/dcssi_/)).
- The design rights belong to the designer, and the design is used in this program with his permission.
- **The MIT License of the source code does not cover** the icon or the logo.
- The icon and logo may not be used outside this project without the designer's prior permission.

## Contact

- Developed by: Mohammed Abd Alrahman — https://www.instagram.com/devlopxx/
- Icon and visual identity: Ahmed Al Basri — https://www.instagram.com/dcssi_/
- Website: https://mohmadev.com/
- Support: support@mohmadev.com
