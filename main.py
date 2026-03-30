import os
import time
import threading
import asyncio
import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from DrissionPage import ChromiumPage, ChromiumOptions
from pyvirtualdisplay import Display  
import uvicorn

app = FastAPI()

state = {
    "is_running": False,
    "status": "Stopped",
    "latest_image": None
}

active_connections = []

def take_instant_screenshot(page):
    """ایک فوری اسکرین شاٹ لے کر اسٹیٹ میں سیٹ کرنے کا فنکشن"""
    try:
        b64 = page.get_screenshot(as_base64=True)
        if b64:
            state["latest_image"] = f"data:image/jpeg;base64,{b64}"
            return True
    except:
        pass
    return False

def drission_thread():
    print("\n[LOG] 🟢 Super Fast Live Feed Thread Start!")
    state["is_running"] = True
    state["status"] = "Starting Monitor..."
    
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    try:
        co = ChromiumOptions()
        co.set_browser_path("/usr/bin/chromium")
        co.headless(False)  
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-blink-features=AutomationControlled') 
        co.set_argument('--window-size=1920,1080')
        
        state["status"] = "Launching Browser..."
        page = ChromiumPage(co)
        
        # 🚨 پہلا اسکرین شاٹ براؤزر کھلتے ہی!
        take_instant_screenshot(page)
        print("[LOG] ✅ Initial Screenshot Captured!")

        # یو آر ایل پر جانے سے پہلے اسٹیٹس اپڈیٹ
        state["status"] = "Navigating to Website..."
        
        # ویب سائٹ لوڈ کرنا شروع کریں (اسے تھریڈ میں نہیں ڈال سکتے، لیکن ہم لوپ میں شاٹس لیں گے)
        # DrissionPage کا get بلاکنگ ہے، اس لیے ہم پہلے ہی شاٹ لے چکے ہیں
        page.get('https://www.smartinmate.com/activate-account-phone.cfm', retry=3, timeout=20)
        
        loop_count = 1
        while state["is_running"]:
            # 🚨 لوپ کے شروع میں ہی اسکرین شاٹ
            take_instant_screenshot(page)
            
            state["status"] = "Page Loaded. Checking Captcha..."

            try:
                # کلاؤڈ فلیر چیک کریں
                if page.ele('text:Success!', timeout=0.1):
                    state["status"] = "Captcha Success!"
                    take_instant_screenshot(page) # آخری کامیابی والا شاٹ
                    break
                
                cf_iframe = page.get_frame('@src^https://challenges.cloudflare.com', timeout=0.5)
                if cf_iframe:
                    verify_text = cf_iframe.ele('text:Verify you are human', timeout=0.5)
                    if verify_text:
                        # ریڈ ڈاٹ ڈرا کریں
                        js_dot = "let d=document.createElement('div');d.style.cssText='position:absolute;left:20px;top:50%;width:20px;height:20px;background:red;border-radius:50%;z-index:9999';document.body.appendChild(d);setTimeout(()=>d.remove(),2000);"
                        cf_iframe.run_js(js_dot)
                        
                        # ڈاٹ کے ساتھ شاٹ
                        time.sleep(0.2)
                        take_instant_screenshot(page)
                        
                        # کلک کریں
                        verify_text.click(offset_x=-45)
                        state["status"] = "Clicked! Waiting for result..."
                        time.sleep(3)

            except Exception as e:
                print(f"[DEBUG] Loop error: {e}")
            
            time.sleep(0.8) # فیڈ کو تیز رکھنے کے لیے تھوڑا کم وقفہ
            loop_count += 1
            
    except Exception as e:
        print(f"[CRITICAL] Error: {e}")
        traceback.print_exc()
        state["status"] = f"Error: {str(e)}"
    finally:
        try:
            page.quit()
            display.stop() 
        except:
            pass
        state["is_running"] = False
        if state["status"] != "Captcha Success!":
            state["status"] = "Stopped"

# باقی FastAPI کا کوڈ وہی رہے گا...

@app.get("/")
async def get():
    return FileResponse("index.html")

async def status_broadcaster():
    last_image = None
    while True:
        if active_connections:
            message = {"status": state["status"], "is_running": state["is_running"]}
            
            # صرف تب بھیجیں جب نئی تصویر ہو
            if state["latest_image"] != last_image:
                message["image"] = state["latest_image"]
                last_image = state["latest_image"]
            
            for connection in active_connections:
                try:
                    await connection.send_json(message)
                except:
                    pass
        await asyncio.sleep(0.4) # براڈکاسٹ کی رفتار تھوڑی تیز

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(status_broadcaster())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "start" and not state["is_running"]:
                threading.Thread(target=drission_thread, daemon=True).start()
            elif data == "stop" and state["is_running"]:
                state["is_running"] = False 
    except WebSocketDisconnect:
        active_connections.remove(websocket)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
