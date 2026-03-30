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
        
        take_instant_screenshot(page)
        print("[LOG] ✅ Initial Screenshot Captured!")

        state["status"] = "Navigating to Website..."
        page.get('https://www.smartinmate.com/activate-account-phone.cfm')
        
        loop_count = 1
        while state["is_running"]:
            take_instant_screenshot(page)
            state["status"] = "Page Loaded. Checking Captcha..."

            try:
                # 1. سکسیس چیک کریں
                if page.ele('text:Success!', timeout=0.1):
                    state["status"] = "Captcha Success!"
                    take_instant_screenshot(page) 
                    break
                
                # 2. 🚨 نیا لاجک: ہم فریم کے اندر نہیں جائیں گے، بس مین پیج پر فریم کا ایلیمنٹ پکڑیں گے
                cf_widget = page.ele('xpath://iframe[contains(@src, "challenges.cloudflare.com")]', timeout=0.5)
                
                if cf_widget:
                    print("[LOG] 🎯 Cloudflare ka dabba bahar se pakar liya!")
                    
                    # ڈبے کی پوزیشن اور سائز حاصل کریں
                    loc = cf_widget.rect.viewport_location # (x, y)
                    size = cf_widget.rect.size # (width, height)
                    
                    # نشانہ سیٹ کریں: ڈبے کے اندر لیفٹ سائیڈ سے 30 پکسل آگے، اور بالکل درمیان میں (یہاں چیک باکس ہوتا ہے)
                    target_x = loc[0] + 30
                    target_y = loc[1] + (size[1] / 2)
                    
                    print(f"[LOG] 🎯 Coordinates set: X={target_x}, Y={target_y}")
                    
                    # 🔴 مین پیج کے اوپر ریڈ ڈاٹ بنائیں (تاکہ کلاؤڈ فلیر بلاک نہ کر سکے)
                    js_dot = f"""
                    let d = document.createElement('div');
                    d.id = 'my-red-dot';
                    d.style.position = 'fixed';
                    d.style.left = '{target_x - 10}px'; /* center the dot */
                    d.style.top = '{target_y - 10}px';
                    d.style.width = '20px';
                    d.style.height = '20px';
                    d.style.backgroundColor = 'red';
                    d.style.border = '2px solid black';
                    d.style.borderRadius = '50%';
                    d.style.zIndex = '999999';
                    d.style.pointerEvents = 'none'; /* کلک اس کے آر پار ہو جائے گا */
                    document.body.appendChild(d);
                    setTimeout(() => d.remove(), 2000);
                    """
                    page.run_js(js_dot)
                    
                    # ڈاٹ بنتے ہی سکرین شاٹ لیں
                    time.sleep(0.3)
                    take_instant_screenshot(page)
                    state["status"] = "Red Dot placed! Clicking now..."
                    print("[LOG] 🖱️ Red dot ban gaya, ab thik wahan click maar rahe hain!")
                    
                    # اصلی ماؤس کو سیدھا ان کوآرڈینیٹس پر لے جا کر کلک ماریں
                    page.actions.move_to_location(target_x, target_y).click()
                    
                    state["status"] = "Clicked! Waiting for result..."
                    time.sleep(4) # کلک کرنے کے بعد 4 سیکنڈ انتظار

            except Exception as e:
                pass
            
            time.sleep(0.8)
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

# ... (FastAPI routes aur websocket setup yahan neechay wese hi rahenge) ...

@app.get("/")
async def get():
    return FileResponse("index.html")

async def status_broadcaster():
    last_image = None
    while True:
        if active_connections:
            message = {"status": state["status"], "is_running": state["is_running"]}
            
            if state["latest_image"] != last_image:
                message["image"] = state["latest_image"]
                last_image = state["latest_image"]
            
            for connection in active_connections:
                try:
                    await connection.send_json(message)
                except:
                    pass
        await asyncio.sleep(0.4)

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
