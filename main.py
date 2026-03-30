import os
import time
import threading
import asyncio
import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from DrissionPage import ChromiumPage, ChromiumOptions
from pyvirtualdisplay import Display  # 👈 ورچوئل سکرین کے لیے
import uvicorn

app = FastAPI()

state = {
    "is_running": False,
    "status": "Stopped",
    "latest_image": None
}

active_connections = []

def drission_thread():
    print("\n[LOG] 🟢 Heavy Duty DrissionPage Thread Start ho gaya hai!")
    state["is_running"] = True
    state["status"] = "Starting Virtual Display & Browser..."
    
    # 🚨 1. ورچوئل مانیٹر آن کریں (1920x1080 فل ایچ ڈی ریزولوشن کے ساتھ)
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    print("[LOG] 🖥️ Virtual Monitor (Xvfb) ON ho gaya!")

    try:
        co = ChromiumOptions()
        co.set_browser_path("/usr/bin/chromium")
        
        # 🚨 2. اب ہم Headless FALSE کر رہے ہیں! (کیونکہ اب ہمارے پاس نقلی سکرین ہے)
        co.headless(False)  
        
        # اینٹی ڈیٹیکشن فلیگز
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-blink-features=AutomationControlled') # بوٹ ڈیٹیکشن کو بائی پاس کرنے کے لیے
        co.set_argument('--window-size=1920,1080')
        
        print("[LOG] 🚀 Chromium Browser (HEADFUL MODE) launch ho raha hai...")
        page = ChromiumPage(co)
        print("[LOG] ✅ Browser launch ho gaya!")

        target_url = 'https://www.smartinmate.com/activate-account-phone.cfm'
        page.get(target_url)
        state["status"] = "Page Loaded. Bypassing Cloudflare..."
        
                loop_count = 1
        while state["is_running"]:
            try:
                b64 = page.get_screenshot(as_base64=True)
                if b64:
                    state["latest_image"] = f"data:image/jpeg;base64,{b64}"
                
                # چیک 1: کیا سکسیس ہو گیا؟
                if page.ele('text:Success!', timeout=0.5):
                    print("[LOG] 🎉 CAPTCHA SUCCESS HO GAYA!")
                    state["status"] = "Captcha Success!"
                    break
                
                # چیک 2: کلاؤڈ فلیر کا باکس ہینڈل کرنا (آپ کے آئیڈیا کے مطابق)
                cf_iframe = page.get_frame('@src^https://challenges.cloudflare.com', timeout=0.5)
                if cf_iframe:
                    # 1. پہلے وہ ٹیکسٹ ڈھونڈیں
                    verify_text = cf_iframe.ele('text:Verify you are human', timeout=1)
                    if verify_text:
                        print("[LOG] 🎯 Text 'Verify you are human' mil gaya!")
                        print("[LOG] 🖱️ Human-like mouse movement: Text ke left side par click kar rahe hain...")
                        
                        # असली انسانوں کی طرح ماؤس موو کروائیں: ٹیکسٹ پر جائیں -> 40 پکسل لیفٹ ہوں -> کلک کریں
                        page.actions.move_to(verify_text).move(offset_x=-40).click()
                        time.sleep(4) # کلک کرنے کے بعد 4 سیکنڈ ویٹ تاکہ وہ پروسیس کرے
                    else:
                        # اگر ٹیکسٹ نہ ملے تو بیک اپ کے طور پر سیدھا باڈی کے لیفٹ پر کلک کریں
                        box = cf_iframe.ele('tag:body', timeout=1) 
                        if box:
                            print("[LOG] ⚠️ Text nahi mila, body ke left par click kar rahe hain...")
                            page.actions.move_to(box).move(offset_x=-40).click()
                            time.sleep(4)
                            
            except Exception as inner_e:
                pass 
            
            time.sleep(1)
            loop_count += 1

            
    except Exception as e:
        print("\n[CRITICAL ERROR] ❌ Browser ya Display error:")
        traceback.print_exc()
        state["status"] = f"Error: {str(e)}"
    finally:
        print("[LOG] 🛑 Closing Browser and Display...")
        try:
            page.quit()
            display.stop() # ورچوئل مانیٹر بھی بند کریں
        except:
            pass
        state["is_running"] = False
        if state["status"] != "Captcha Success!":
            state["status"] = "Stopped"
        print("[LOG] 🔴 Thread execution mukammal ho gayi.\n")

@app.get("/")
async def get():
    return FileResponse("index.html")

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
