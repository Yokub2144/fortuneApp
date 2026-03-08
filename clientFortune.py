import socket
from customtkinter import *
from tkinter import messagebox

set_appearance_mode("dark")
app = CTk()
app.title("🔮 Fortune Client")
app.geometry("450x550")

# สร้าง Socket รอไว้เพียงครั้งเดียว
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
PORT = 65432

def request_prediction():
    server_ip = ip_entry.get().strip()
    age = age_entry.get().strip()
    category = category_var.get()
    
    if not server_ip or not age:
        messagebox.showwarning("เตือน", "กรุณากรอก IP Server และ อายุของคุณ")
        return

    if not age.isdigit():
        messagebox.showwarning("เตือน", "กรุณากรอกอายุเป็นตัวเลขเท่านั้น")
        return

    try:
        # ส่งข้อมูลไปยัง Server
        client_socket.sendto(category.encode('utf-8'), (server_ip, PORT))
        
        # ตั้งเวลารอ (Timeout)
        client_socket.settimeout(3.0)
        data, _ = client_socket.recvfrom(1024)
        
        # แสดงผลลัพธ์
        result_label.configure(
            text=f"อายุ {age} ปี - ดวงด้าน{category}\n\n✨ {data.decode('utf-8')} ✨",
            text_color="#00FFCC"
        )
    except socket.timeout:
        messagebox.showerror("Error", "ติดต่อ Server ไม่ได้\nตรวจสอบ IP หรือ Firewall ของเครื่อง Server")
    except Exception as e:
        messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {e}")

# --- Client UI ---
CTkLabel(app, text="🔮 พยากรณ์ดวงชะตา", font=("Helvetica", 26, "bold")).pack(pady=25)

# ส่วนตั้งค่า Server
server_frame = CTkFrame(app)
server_frame.pack(pady=10, padx=20, fill="x")
CTkLabel(server_frame, text="IP Server:").grid(row=0, column=0, padx=10, pady=10)
ip_entry = CTkEntry(server_frame, placeholder_text="เช่น 192.168.1.50", width=180)
ip_entry.grid(row=0, column=1, padx=10)

# ส่วนข้อมูลผู้ใช้
input_frame = CTkFrame(app, fg_color="transparent")
input_frame.pack(pady=20)
CTkLabel(input_frame, text="อายุของคุณ:").grid(row=0, column=0, padx=10)
age_entry = CTkEntry(input_frame, width=80)
age_entry.grid(row=0, column=1)

# หมวดหมู่
category_var = StringVar(value="ความรัก")
category_menu = CTkOptionMenu(app, values=["ความรัก", "การเรียน", "การเงิน", "การทำงาน"], 
                             variable=category_var, width=200)
category_menu.pack(pady=10)

# ปุ่มกด
predict_btn = CTkButton(app, text="ทำนายดวง", fg_color="#8A2BE2", hover_color="#6A5ACD",
                        font=("Helvetica", 14, "bold"), command=request_prediction)
predict_btn.pack(pady=25)

# ผลลัพธ์
result_label = CTkLabel(app, text="กรอก IP แล้วกดปุ่มเพื่อเริ่มทำนาย", 
                        font=("Helvetica", 16), wraplength=380)
result_label.pack(pady=10, padx=20)

app.mainloop()