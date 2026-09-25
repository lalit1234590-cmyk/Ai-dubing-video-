from flask import Flask, request, render_template_string, send_from_directory, jsonify
import os, uuid, subprocess, asyncio
from werkzeug.utils import secure_filename

app=Flask(__name__)
UPLOAD="/tmp/uploads"
OUTPUT="/tmp/outputs"
os.makedirs(UPLOAD,exist_ok=True)
os.makedirs(OUTPUT,exist_ok=True)
app.config["MAX_CONTENT_LENGTH"]=500*1024*1024
ALLOWED={".mp4",".mkv",".mov",".webm",".avi"}

def run(cmd):
    subprocess.run(cmd,check=True)

async def tts(text,out_file,target):
    import edge_tts
    voices={"hi":"hi-IN-SwaraNeural","en":"en-US-AriaNeural","ko":"ko-KR-SunHiNeural"}
    await edge_tts.Communicate(text,voice=voices.get(target,"hi-IN-SwaraNeural")).save(out_file)

@app.get("/")
def home():
    return render_template_string('<!doctype html><html lang="hi"><head>\n<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<title>AI Video Dubbing</title>\n<style>\n*{box-sizing:border-box;margin:0;padding:0;}\nbody{font-family:Arial,sans-serif;background:#f4f6fb;padding:15px;display:flex;align-items:center;justify-content:center;min-height:100vh;}\n.card{width:100%;max-width:450px;background:#fff;padding:20px;border-radius:18px;box-shadow:0 4px 20px rgba(0,0,0,0.08);}\nh1{font-size:22px;margin-bottom:8px;}\np{font-size:14px;color:#555;margin-bottom:15px;line-height:1.4;}\nlabel{font-size:14px;font-weight:bold;color:#333;display:block;margin-top:10px;}\ninput,select,button{width:100%;padding:12px;margin:5px 0 12px;border-radius:10px;border:1px solid #ccc;font-size:15px;font-family:inherit;}\nbutton{background:#111827;color:#fff;font-size:16px;font-weight:bold;cursor:pointer;margin-top:10px;margin-bottom:0;border:none;}\nbutton:active{background:#1f2937;}\n.status{margin-top:15px;white-space:pre-wrap;font-size:14px;font-weight:bold;}\n</style></head><body><div class="card">\n<h1>🎙️ AI Video Dubbing</h1>\n<p>Japanese / Chinese / Korean / English वीडियो को Hindi या दूसरी भाषा में dub करें।</p>\n<label>Video</label><input id="video" type="file" accept="video/*">\n<label>Original language</label><select id="source"><option value="ja">Japanese</option><option value="zh-CN">Chinese</option><option value="en">English</option><option value="ko">Korean</option></select>\n<label>Dub language</label><select id="target"><option value="hi">Hindi</option><option value="en">English</option><option value="ko">Korean</option></select>\n<button onclick="dub()">🎬 Start Dubbing</button><div id="status" class="status"></div>\n</div><script>\nasync function dub(){\nlet f=document.getElementById("video").files[0];if(!f)return alert("वीडियो चुनें");\nlet fd=new FormData();fd.append("video",f);fd.append("source",source.value);fd.append("target",target.value);\nstatus.textContent="⏳ Video process हो रहा है...";\nlet r=await fetch("/dub",{method:"POST",body:fd});let d=await r.json();\nif(!r.ok){status.textContent="❌ "+(d.error||"Error");return}\nstatus.innerHTML="✅ Dubbing complete!<br><br><a href='"+d.download+"' style='color:#2563eb;text-decoration:underline;'>⬇️ Dubbed Video Download</a>";\n}\n</script></body></html>\n')

@app.post("/dub")
def dub():
    video=request.files.get("video")
    source=request.form.get("source","ja")
    target=request.form.get("target","hi")
    if not video or not video.filename:
        return jsonify(error="Video select करें"),400
    ext=os.path.splitext(secure_filename(video.filename))[1].lower()
    if ext not in ALLOWED:
        return jsonify(error="Unsupported video format"),400
    job=uuid.uuid4().hex
    src=os.path.join(UPLOAD,job+ext)
    wav=os.path.join(UPLOAD,job+".wav")
    voice=os.path.join(OUTPUT,job+".mp3")
    final=os.path.join(OUTPUT,job+"_dubbed.mp4")
    video.save(src)
    try:
        run(["ffmpeg","-y","-i",src,"-vn","-ac","1","-ar","16000",wav])
        from faster_whisper import WhisperModel
        model=WhisperModel("tiny",compute_type="int8")
        segs,_=model.transcribe(wav,language=source)
        original=" ".join(s.text.strip() for s in segs)
        if not original:
            return jsonify(error="Speech नहीं मिली"),400
        from deep_translator import GoogleTranslator
        translated=GoogleTranslator(source=source,target=target).translate(original)
        asyncio.run(tts(translated,voice,target))
        run(["ffmpeg","-y","-i",src,"-i",voice,"-map","0:v:0","-map","1:a:0","-c:v","copy","-shortest",final])
        return jsonify(ok=True,download="/download/"+os.path.basename(final),
                       original_text=original[:5000],translated_text=translated[:5000])
    except Exception as e:
        return jsonify(error=str(e)),500

@app.get("/download/<name>")
def download(name):
    return send_from_directory(OUTPUT,name,as_attachment=True)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")))
