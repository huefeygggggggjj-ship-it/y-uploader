import os, tempfile, requests
from flask import Flask, request, render_template_string, redirect

# كل الإعدادات من Environment Variables في الاستضافة
PASSWORD = os.getenv("APP_PASSWORD", "")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")  # رابط موقعك
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN", "")
YT_ID = os.getenv("YT_CLIENT_ID", "")
YT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH = os.getenv("YT_REFRESH_TOKEN", "")
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

PAGE = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>رافع الفيديوهات</title>
<style>
body{font-family:system-ui,sans-serif;max-width:520px;margin:0 auto;padding:18px;background:#f6f6f8;color:#222}
form{background:#fff;padding:16px;border-radius:14px;display:grid;gap:12px}
input[type=text],input[type=password],textarea{width:100%;padding:12px;border:1px solid #ccc;border-radius:8px;font:inherit;box-sizing:border-box}
button{padding:14px;border:0;border-radius:10px;background:#6c3df4;color:#fff;font-size:17px}
label.c{display:flex;gap:8px;align-items:center}.r{margin-top:14px;background:#fff;padding:14px;border-radius:14px;word-break:break-all}
</style></head><body><h2>📤 رافع الفيديوهات</h2>
<form method="post" enctype="multipart/form-data" onsubmit="b.disabled=true;b.textContent='جاري الرفع... استني'">
<input type="password" name="pw" placeholder="كلمة السر" required>
<input type="file" name="video" accept="video/*" required>
<input type="text" name="title" placeholder="العنوان" required>
<textarea name="desc" rows="3" placeholder="الوصف"></textarea>
<label class="c"><input type="checkbox" name="p" value="youtube" checked> يوتيوب</label>
<label class="c"><input type="checkbox" name="p" value="facebook" checked> فيسبوك</label>
<label class="c"><input type="checkbox" name="p" value="instagram"> إنستغرام (قريباً)</label>
<label class="c"><input type="checkbox" name="p" value="tiktok"> تيك توك (قريباً)</label>
<button name="b" id="b">ارفعي</button></form>
{% if results %}<div class="r">{% for n,m in results %}<p><b>{{n}}:</b> {{m}}</p>{% endfor %}</div>{% endif %}
</body></html>"""


def upload_youtube(path, title, desc):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    if not YT_REFRESH:
        return "ناقص YT_REFRESH_TOKEN (افتحي /yt/login مرة وحدة)"
    creds = Credentials(None, refresh_token=YT_REFRESH, client_id=YT_ID, client_secret=YT_SECRET,
                        token_uri="https://oauth2.googleapis.com/token", scopes=YT_SCOPES)
    yt = build("youtube", "v3", credentials=creds)
    body = {"snippet": {"title": title, "description": desc}, "status": {"privacyStatus": "private"}}
    res = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(path, resumable=True)).execute()
    return f"تم ✅ https://youtu.be/{res['id']}"


def upload_facebook(path, title, desc):
    if not (FB_PAGE_ID and FB_PAGE_TOKEN):
        return "ناقص FB_PAGE_ID أو FB_PAGE_TOKEN"
    with open(path, "rb") as f:
        r = requests.post(f"https://graph-video.facebook.com/v21.0/{FB_PAGE_ID}/videos",
                          data={"access_token": FB_PAGE_TOKEN, "title": title, "description": desc},
                          files={"source": f}, timeout=3000)
    j = r.json()
    return f"تم ✅ (id {j['id']})" if "id" in j else f"فشل: {j}"


HANDLERS = {
    "youtube": ("يوتيوب", upload_youtube), "facebook": ("فيسبوك", upload_facebook),
    "instagram": ("إنستغرام", lambda *a: "لسا مش مفعّل"), "tiktok": ("تيك توك", lambda *a: "لسا مش مفعّل")}


@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    if request.method == "POST":
        if not PASSWORD or request.form.get("pw") != PASSWORD:
            return render_template_string(PAGE, results=[("خطأ", "كلمة السر غلط")])
        f = request.files["video"]
        tmp = os.path.join(tempfile.gettempdir(), os.path.basename(f.filename))
        f.save(tmp)
        for key in request.form.getlist("p"):
            name, fn = HANDLERS[key]
            try:
                msg = fn(tmp, request.form["title"], request.form.get("desc", ""))
            except Exception as e:
                msg = f"خطأ: {e}"
            results.append((name, msg))
        os.remove(tmp)
    return render_template_string(PAGE, results=results)


def yt_flow():
    from google_auth_oauthlib.flow import Flow
    cfg = {"web": {"client_id": YT_ID, "client_secret": YT_SECRET,
                   "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                   "token_uri": "https://oauth2.googleapis.com/token"}}
    return Flow.from_client_config(cfg, YT_SCOPES, redirect_uri=BASE_URL + "/yt/callback")


@app.route("/yt/login")  # خطوة تتعمل مرة وحدة لربط يوتيوب
def yt_login():
    flow = yt_flow()
    url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    app.config["YT_VERIFIER"] = flow.code_verifier
    return redirect(url)


@app.route("/yt/callback")
def yt_callback():
    flow = yt_flow()
    flow.code_verifier = app.config.get("YT_VERIFIER")
    flow.fetch_token(authorization_response=request.url.replace("http://", "https://"))
    return ("<p dir=rtl>انسخي الكود ده وحطيه في Environment Variable اسمها "
            "<b>YT_REFRESH_TOKEN</b> وبعدين امسحي الصفحة دي:</p><pre style='word-break:break-all'>"
            + (flow.credentials.refresh_token or "مفيش توكن - جربي /yt/login تاني") + "</pre>")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
