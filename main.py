import os
import time
import threading
import asyncio
import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from DrissionPage import ChromiumPage, ChromiumOptions
import uvicorn

app = FastAPI()

state = {
    "is_running": False,
    "status": "Stopped",
    "latest_image": None
}

active_connections = []

def drission_thread():
    print("\n[LOG] 🟢 DrissionPage Thread Start ho gaya hai!")
    state["is_running"] = True
    state["status"] = "Starting DrissionPage Browser..."
    
    try:
        print("[LOG] ⚙️ Chromium Options set kar rahe hain...")
        co = ChromiumOptions()
        co.headless(True)  
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        co.set_argument('--disable-dev-shm-usage') # 🚨 Railway/Docker ke liye sab se zaroori flag
        
        print("[LOG] 🚀 Chromium Browser launch ho raha hai. Please wait...")
        page = ChromiumPage(co)
        print("[LOG] ✅ Browser successfully launch ho gaya!")

        target_url = 'https://www.smartinmate.com/activate-account-phone.cfm'
        print(f"[LOG] 🌍 URL par ja rahe hain: {target_url}")
        page.get(target_url)
        print("[LOG] 📄 Page load ho gaya hai. Captcha ka wait kar rahe hain...")
        
        state["status"] = "Page Loaded. Waiting for Captcha..."
        
        loop_count = 1
        while state["is_running"]:
            try:
                print(f"[LOG] 📸 Screenshot attempt #{loop_count}...")
                b64 = page.get_screenshot(as_base64=True)
                if b64:
                    print(f"[LOG] ✔️ Screenshot #{loop_count} capture ho gaya aur frontend ko bhej diya.")
                    state["latest_image"] = f"data:image/jpeg;base64,{b64}"
                else:
                    print(f"[LOG] ⚠️ Screenshot #{loop_count} capture nahi ho saka.")
                
                print("[LOG] 🔍 Check kar rahe hain ke Captcha Success hua ya nahi...")
                if page.ele('text:Success!', timeout=0.1):
                    print("[LOG] 🎉 CAPTCHA SUCCESS HO GAYA!")
                    state["status"] = "Captcha Success!"
                    break
                else:
                    print("[LOG] ⏳ Captcha abhi pass nahi hua, waiting...")

            except Exception as inner_e:
                print(f"[ERROR] ❌ Loop ke andar error aaya: {str(inner_e)}")
            
            time.sleep(1)
            loop_count += 1
            
    except Exception as e:
        print("\n[CRITICAL ERROR] ❌ Browser launch ya page load karte waqt error aa gaya:")
        print(str(e))
        traceback.print_exc()  # Yeh error ki poori detail terminal me print karega
        state["status"] = f"Error: {str(e)}"
    finally:
        print("[LOG] 🛑 Closing Browser and Thread...")
        try:
            page.quit()
            print("[LOG] ✔️ Browser close ho gaya.")
        except Exception as q_e:
            print(f"[LOG] ⚠️ Browser close karte waqt error: {str(q_e)}")
            
        state["is_running"] = False
        if state["status"] != "Captcha Success!":
            state["status"] = "Stopped"
        print("[LOG] 🔴 Thread execution mukammal ho gayi.\n")

@app.get("/")
async def get():
    print("[LOG] 🌐 Frontend page (index.html) kisi ne open kiya.")
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
    print("[LOG] 🚀 FastAPI Server Start ho gaya hai!")
    asyncio.create_task(status_broadcaster())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    print(f"[LOG] 🔌 Naya WebSocket connection ban gaya! Total connections: {len(active_connections)}")
    
    await websocket.send_json({
        "status": state["status"],
        "is_running": state["is_running"]
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"[LOG] 📩 Frontend se message aaya: '{data}'")
            
            if data == "start" and not state["is_running"]:
                print("[LOG] ▶️ Start command mili, thread start kar rahe hain...")
                threading.Thread(target=drission_thread, daemon=True).start()
            elif data == "stop" and state["is_running"]:
                print("[LOG] ⏹️ Stop command mili, process rok rahe hain...")
                state["is_running"] = False 
                state["status"] = "Stopping..."
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"[LOG] 🔌 WebSocket connection disconnect ho gaya. Baqi connections: {len(active_connections)}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"[LOG] 🌍 Server host 0.0.0.0 aur port {port} par run hone laga hai...")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
