import socket
import threading
from datetime import datetime
from customtkinter import *
from lib import get_fortune, get_host_ip

set_appearance_mode("dark")
app = CTk()
app.title("🔮 Fortune Server Control (UDP)")
app.geometry("600x500")

def add_log(message):
    """แสดง Log บนหน้าจอ Server"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_text.configure(state="normal")
    log_text.insert("end", f"[{timestamp}] {message}\n")
    log_text.configure(state="disabled")
    log_text.see("end")

def run_udp_server():
    """ฟังก์ชันทำงานของ Server (รันใน Background Thread)"""
    HOST = '0.0.0.0' # เปิดรับทุก IP
    PORT = 65432
    
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST, PORT))
    
    my_ip = get_host_ip()
    app.after(0, lambda: add_log(f"🚀 Server Online at {my_ip}:{PORT}"))
    app.after(0, lambda: info_label.configure(text=f"Server IP: {my_ip} | Port: {PORT}"))

    while True:
        try:
            data, addr = server.recvfrom(1024)
            category = data.decode('utf-8')
            
            # บันทึก Log เมื่อมีคนมาดูดวง
            app.after(0, lambda a=addr, c=category: add_log(f"📩 [{a[0]}] ดูดวงหมวด: {c}"))
            
            # ส่งคำทำนายกลับ
            prediction = get_fortune(category)
            server.sendto(prediction.encode('utf-8'), addr)
            
        except Exception as e:
            app.after(0, lambda err=e: add_log(f"❌ Error: {err}"))

# --- Server UI ---
CTkLabel(app, text="🔮 Fortune Server Management", font=("Helvetica", 22, "bold")).pack(pady=15)
info_label = CTkLabel(app, text="กำลังเริ่มต้น...", text_color="#00FFCC")
info_label.pack(pady=5)

log_frame = CTkFrame(app)
log_frame.pack(pady=15, padx=20, fill="both", expand=True)
CTkLabel(log_frame, text="Activity Logs:").pack(anchor="w", padx=10, pady=5)

log_text = CTkTextbox(log_frame, font=("Consolas", 12))
log_text.pack(fill="both", expand=True, padx=10, pady=10)
log_text.configure(state="disabled")

# เริ่ม Server แบบ Threading เพื่อไม่ให้หน้าจอดับ
threading.Thread(target=run_udp_server, daemon=True).start()

app.mainloop()