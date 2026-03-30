import os
import time
import threading
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from DrissionPage import ChromiumPage, ChromiumOptions
import uvicorn

app = FastAPI()

# گلوبل سٹیٹ (تاکہ پیج ریفریش ہونے پر بھی پراسیس اور ہسٹری برقرار رہے)
state = {
    "is_running": False,
    "status": "Stopped",
    "latest_image": None
}

active_connections = []

def drission_thread():
    state["is_running"] = True
    state["status"] = "Starting DrissionPage Browser..."
    
    co = ChromiumOptions()
    # Railway سرور پر سکرین نہیں ہوتی، اس لیے اسے True رکھنا ضروری ہے
    co.headless(True)  
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    
    try:
        page = ChromiumPage(co)
        page.get('https://www.smartinmate.com/activate-account-phone.cfm')
        state["status"] = "Page Loaded. Waiting for Captcha..."
        
        while state["is_running"]:
            try:
                # اسکرین شاٹ کو Base64 فارمیٹ میں لینا
                b64 = page.get_screenshot(as_base64=True)
                if b64:
                    state["latest_image"] = f"data:image/jpeg;base64,{b64}"
                
                # چیک کرنا کہ کیا کلاؤڈ فلیر پاس ہو گیا ہے
                if page.ele('text:Success!', timeout=0.1):
                    state["status"] = "Captcha Success!"
                    # یہاں آپ کوکیز وغیرہ نکال سکتے ہیں
                    # cookies = page.cookies()
                    break
            except Exception:
                pass
            
            time.sleep(1)  # ہر 1 سیکنڈ بعد کیپچر لے گا
            
    except Exception as e:
        state["status"] = f"Error: {str(e)}"
    finally:
        try:
            page.quit()
        except:
            pass
        state["is_running"] = False
        if state["status"] != "Captcha Success!":
            state["status"] = "Stopped"

# ہوم پیج پر روٹ ڈائریکٹری سے ڈائریکٹ HTML فائل ریٹرن کروانا
@app.get("/")
async def get():
    return FileResponse("index.html")

# بیک گراؤنڈ ٹاسک جو ہر وقت کنیکٹڈ کلائنٹس کو اپڈیٹس بھیجتا رہے گا
async def status_broadcaster():
    last_status = None
    last_image = None
    while True:
        if active_connections:
            message = {}
            if state["status"] != last_status:
                message["status"] = state["status"]
                last_status = state["status"]
            
            if state["latest_image"] != last_image:
                message["image"] = state["latest_image"]
                last_image = state["latest_image"]
                
            message["is_running"] = state["is_running"]

            if message:
                for connection in active_connections:
                    try:
                        await connection.send_json(message)
                    except:
                        pass
        await asyncio.sleep(0.5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(status_broadcaster())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    # کنیکٹ ہوتے ہی موجودہ سٹیٹس بھیجنا
    await websocket.send_json({
        "status": state["status"],
        "is_running": state["is_running"]
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            if data == "start" and not state["is_running"]:
                threading.Thread(target=drission_thread, daemon=True).start()
            elif data == "stop" and state["is_running"]:
                state["is_running"] = False 
                state["status"] = "Stopping..."
    except WebSocketDisconnect:
        active_connections.remove(websocket)

# Railway پر چلانے کے لیے Host اور Port کی سیٹنگ
if __name__ == "__main__":
    # Railway خودبخود PORT کا انوائرنمنٹ ویری ایبل دیتا ہے
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
