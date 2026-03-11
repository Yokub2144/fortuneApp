import customtkinter as ctk
import socket
import json
import threading
import os
from PIL import Image, ImageTk
import time
# ตั้งค่าธีม
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class PokdengClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Pokdeng Online - Modern Casino")
        self.geometry("450x550")
        
        # คอนฟิกเส้นทางไฟล์
        self.card_path = "assets/card"
        self.image_path = "assets/image"
        
        # ข้อมูล Network & Game State
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_addr = None
        self.player_name = ""
        self.room_id = ""
        self.is_host = False
        self.my_balance = 5000
        
        # ตัวแปรเก็บรูปภาพ (ป้องกัน Garbage Collection)
        self.table_photo = None
        self.player_widgets = []

        self.setup_connection_ui()

    # --- Utility Functions ---
    def clear_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

    def send_to_server(self, data):
        if self.server_addr:
            self.sock.sendto(json.dumps(data).encode(), self.server_addr)

    # --- 1. Connection UI ---
    def setup_connection_ui(self):
        self.clear_screen()
        self.geometry("450x550")
        
        frame = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=20)
        frame.pack(expand=True, padx=30, pady=30, fill="both")

        ctk.CTkLabel(frame, text="♠️POKDENG♣️", font=("Arial", 32, "bold"), text_color="#60a5fa").pack(pady=(30,10))
        
        self.ip_entry = ctk.CTkEntry(frame, placeholder_text="Server IP (e.g. 127.0.0.1)", width=250, height=45)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack(pady=10)

        self.name_entry = ctk.CTkEntry(frame, placeholder_text="Enter Your Name", width=250, height=45)
        self.name_entry.pack(pady=10)

        btn = ctk.CTkButton(frame, text="ENTER LOBBY", font=("Arial", 16, "bold"), height=50, width=250,
                            command=self.connect_to_server)
        btn.pack(pady=30)

    def connect_to_server(self):
        target_ip = self.ip_entry.get() or "127.0.0.1"
        self.player_name = self.name_entry.get() or "Player"
        self.server_addr = (target_ip, 5005)

        self.send_to_server({"action": "enter_lobby", "name": self.player_name})
        threading.Thread(target=self.receive_data, daemon=True).start()
        self.show_lobby_ui()

    # --- 2. Lobby UI ---
    def show_lobby_ui(self):
        self.clear_screen()
        self.geometry("800x600")
        self.configure(fg_color="#0f172a")

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(header, text=f"Welcome, {self.player_name}", font=("Arial", 20, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Create Room", fg_color="#16a34a", command=self.req_create_room).pack(side="right")

        self.room_list_frame = ctk.CTkScrollableFrame(self, fg_color="#1e293b", label_text="Available Rooms")
        self.room_list_frame.pack(expand=True, fill="both", padx=20, pady=10)

    def update_room_list(self, rooms):
        for widget in self.room_list_frame.winfo_children():
            widget.destroy()

        for room in rooms:
            f = ctk.CTkFrame(self.room_list_frame, fg_color="#334155")
            f.pack(fill="x", pady=5, padx=10)
            
            info = f"Room ID: {room['room_id']}  |  Host: {room['host']} ({room['count']}/6)"
            ctk.CTkLabel(f, text=info, font=("Arial", 14)).pack(side="left", padx=15, pady=10)
            
            ctk.CTkButton(f, text="Join", width=80, 
                          command=lambda r=room['room_id']: self.join_room(r)).pack(side="right", padx=10)

    def req_create_room(self):
        dialog = ctk.CTkInputDialog(text="ระบุรหัสผ่านห้อง (ว่างไว้ถ้าไม่ใช้):", title="Create Private Room")
        room_pass = dialog.get_input()
        
        if room_pass is not None: # ถ้าไม่ได้กด Cancel
            self.send_to_server({
                "action": "create", 
                "name": self.player_name,
                "password": room_pass  # ส่งรหัสไปที่ Server ด้วย
            })

    def join_room(self, room_id):
        dialog = ctk.CTkInputDialog(text=f"กรุณาใส่รหัสผ่านสำหรับห้อง {room_id}:", title="Room Password")
        input_pass = dialog.get_input()
        
        if input_pass is not None:
            self.send_to_server({
                "action": "join", 
                "room_id": room_id, 
                "name": self.player_name,
                "password": input_pass # ส่งรหัสที่ผู้เล่นกรอกไปเช็ค
            })

    # --- 3. Game Table UI (The Core) ---
    def show_game_table(self):
        self.clear_screen()
        self.geometry("900x700")
        self.configure(fg_color="#0f172a")

        # ==========================================
        # ส่วนที่ 1: พื้นหลัง (Layer 1 - Canvas & Table)
        # ==========================================
        self.bg_canvas = ctk.CTkCanvas(self, width=900, height=700, bg="#0f172a", highlightthickness=0)
        self.bg_canvas.pack(fill="both", expand=True)
        
        try:
            table_path = os.path.join(self.image_path, "table.png")
            raw_table = Image.open(table_path).resize((900, 520), Image.Resampling.LANCZOS)
            self.table_photo = ImageTk.PhotoImage(raw_table) 
            self.bg_canvas.create_image(550, 350, image=self.table_photo)
        except:
            self.bg_canvas.create_oval(150, 150, 950, 550, fill="#14532d")

        # ==========================================
        # ส่วนที่ 2: ตำแหน่งผู้เล่น (Layer 2 - Seats & Cards)
        # ==========================================
        self.seats = [
            {"x": 550, "y": 70},   # 0: บน
            {"x": 1000, "y": 210}, # 1: ขวาบน
            {"x": 1000, "y": 450}, # 2: ขวาล่าง
            {"x": 550, "y": 600},  # 3: ล่าง (ตัวเรา)
            {"x": 100, "y": 450},  # 4: ซ้ายล่าง
            {"x": 100, "y": 210},  # 5: ซ้ายบน
        ]
        offsets = [
            {"dx": 0,    "dy": 85},   # 0
            {"dx": -210, "dy": -20},  # 1
            {"dx": -210, "dy": -100}, # 2
            {"dx": 0,    "dy": -220}, # 3
            {"dx": 210,  "dy": -100}, # 4
            {"dx": 210,  "dy": -20},  # 5
        ]

        try:
            av_raw = Image.open(os.path.join(self.image_path, "Avatar.png")).resize((65, 65))
            self.avatar_photo = ImageTk.PhotoImage(av_raw)
        except: self.avatar_photo = None

        self.player_objects = [] 
        for i, pos in enumerate(self.seats):
            # 2.1 วาด Avatar และ ชื่อ
            self.bg_canvas.create_image(pos["x"], pos["y"], image=self.avatar_photo)
            name_id = self.bg_canvas.create_text(
                pos["x"], pos["y"] + 50, 
                text="ว่าง", fill="#cbd5e1", font=("Arial", 13, "bold")
            )


            # 2.3 💡 เก็บ card_container เข้าไปใน Dictionary ด้วย! (สำคัญมาก)
            self.player_objects.append({"name_id": name_id})

        # ==========================================
        # ส่วนที่ 3: ปุ่มควบคุมเกม (Layer 3 - Game Controls)
        # ==========================================
        if self.is_host:
            self.start_btn = ctk.CTkButton(self.bg_canvas, text="เริ่มเกม", fg_color="#e11d48", hover_color="#be123c",
                                           font=("Arial", 16, "bold"), width=120, height=40, command=self.send_start_command)
            self.bg_canvas.create_window(550, 320, window=self.start_btn, tags="start_button_tag")
        else:
            self.bg_canvas.create_text(550, 320, text="รอเจ้ามือเริ่มเกม...", fill="#ff0000", font=("Arial", 18, "bold"), tags="waiting_text_tag")

        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.place(relx=0.95, rely=0.92, anchor="e")
        
        self.hit_btn = ctk.CTkButton(action_frame, text="จั่ว (HIT)", fg_color="#16a34a", width=90, 
                                     state="disabled", command=lambda: self.send_action("hit"))
        self.hit_btn.pack(side="left", padx=5)
        
        self.stand_btn = ctk.CTkButton(action_frame, text="อยู่ (STAY)", fg_color="#2563eb", width=90, 
                                       state="disabled", command=lambda: self.send_action("stand"))
        self.stand_btn.pack(side="left", padx=5)

        # ตัวแปรสำหรับระบบ Turn และ Timer
        self.timer_id = None
        self.my_current_score = 0
        # ==========================================
        # ส่วนที่ 4: ข้อมูลห้อง & ปุ่มออก (Layer 4 - Top UI Overlay)
        # ==========================================
        
        # 4.1 ข้อมูลห้อง (ตั้งความสูงเป็น 60 เพื่อให้พอดี 2 บรรทัด ID และ Password)
        room_tag = ctk.CTkFrame(self.bg_canvas, fg_color="#1e293b", corner_radius=10, width=120, height=60)
        room_tag.pack_propagate(False) # <--- ตัวนี้แหละที่ป้องกันไม่ให้มันขยายไปทับโต๊ะ
        self.bg_canvas.create_window(20, 20, window=room_tag, anchor="nw")
        
        ctk.CTkLabel(room_tag, text=f"ID: {self.room_id}", font=("Arial", 14, "bold"), text_color="#60a5fa").pack(pady=(5,0))
        # ใช้ getattr เผื่อกรณีที่ห้องนั้นไม่ได้ตั้ง password ไว้ ตัวแปรจะได้ไม่ error
        ctk.CTkLabel(room_tag, text=f"Pass: {getattr(self, 'password', '-')}", font=("Arial", 12), text_color="#94a3b8").pack()

        # 4.2 ปุ่มออก (แก้พิกัด X จาก 0 เป็น 880 เพื่อให้อยู่มุมขวาบนของจอ 900)
        self.exit_btn = ctk.CTkButton(self, text="❌ ออก", fg_color="#334155", hover_color="#e11d48",
                                      width=80, height=32, font=("Arial", 12, "bold"), command=self.leave_room)
        # วางที่พิกัด X=880 ยึดมุมขวาบน (ne)
        self.exit_btn.place(x=880, y=20, anchor="ne")
    def leave_room(self):
        # 1. ส่งข้อมูลไปบอก Server ว่าเราขอออกจากห้อง
        if hasattr(self, 'room_id') and self.room_id:
            self.send_to_server({
                "action": "leave",
                "room_id": self.room_id,
                "name": self.player_name
            })
        
        # 2. รีเซ็ตค่าตัวแปรของห้อง
        self.room_id = None
        self.is_host = False
        self.password = None
        
        # 3. ล้างหน้าจอและกลับไปหน้า Lobby
        self.clear_screen()
        if hasattr(self, 'show_lobby'): 
            self.show_lobby() 
        else:
            print("ยังไม่มีฟังก์ชันกลับหน้า Lobby")
    def receive_data(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(8192)
                msg = json.loads(data.decode())
                status = msg.get("status")

                if status == "lobby_update":
                    self.after(0, lambda: self.update_room_list(msg.get("rooms", [])))
                
                # --- ส่วนที่เพิ่มใหม่: จัดการข้อผิดพลาด (เช่น รหัสผ่านผิด หรือห้องเต็ม) ---
                elif status == "error":
                    error_msg = msg.get("message", "เกิดข้อผิดพลาดบางอย่าง")
                    from tkinter import messagebox
                    # ใช้ self.after เพื่อให้เด้ง Popup บน Main Thread ของ GUI
                    self.after(0, lambda: messagebox.showerror("แจ้งเตือน", error_msg))
                # ------------------------------------------------------------

                elif status in ["created", "joined"]:
                    self.room_id = msg.get("room_id")
                    self.is_host = msg.get("is_host", False)
                    self.after(0, self.show_game_table)
                    self.after(100, lambda: self.send_to_server({
                        "action": "get_room_update", 
                        "room_id": self.room_id
                    }))
                
                elif status == "room_update":
                    players_data = msg.get("players", [])
                    self.after(0, lambda p=players_data: self.update_table_players(p))
                
                elif status == "game_started":
                    self.after(0, lambda: self.display_my_cards(msg))
                
                elif status == "show_all_cards":
                    self.after(0, lambda: self.display_all_hands(msg.get("all_players_data", {})))
                elif status == "turn_update":
                    self.after(0, lambda m=msg: self.update_turn_ui(m))    
            except Exception as e:
                print(f"Receive Error: {e}")
                break

    def update_table_players(self, players):
        # --- พิมพ์ข้อมูลออกมาดูใน Terminal (เพื่อให้เรารู้ว่า Server ส่งอะไรมา) ---
        if not hasattr(self, 'player_objects') or len(self.player_objects) < 6:
            # ถ้ายังสร้างไม่เสร็จ ให้ดีเลย์รอไปอีก 100 มิลลิวินาที แล้วค่อยลองอัปเดตใหม่
            self.after(100, lambda: self.update_table_players(players))
            return

        # --- โค้ดเดิมของคุณต่อจากตรงนี้ ---
        print(f"\n[DEBUG] ห้องอัปเดตรายชื่อ!")
        print(f"[DEBUG] ชื่อของฉันคือ: '{self.player_name}'")
        print(f"[DEBUG] ข้อมูลที่ Server ส่งมา: {players}")
        
        # 1. รีเซ็ตทุกที่นั่งให้เป็น "ว่าง"
        for obj in self.player_objects:
            self.bg_canvas.itemconfigure(obj["name_id"], text="ว่าง", fill="gray")
            
        self.player_seat_map = {} 
        other_seats = [4, 5, 0, 1, 2] # ลำดับเก้าอี้คนอื่น
        other_idx = 0

        # 2. จัดการข้อมูลเผื่อ Server ส่งมาแปลกๆ
        if isinstance(players, dict):
            players_list = list(players.values())
        elif isinstance(players, list):
            players_list = players
        else:
            players_list = []

        # 3. เริ่มจัดคนลงที่นั่ง
        for p_data in players_list:
            # ดึงชื่อออกมา และใช้ .strip() เพื่อตัดช่องว่าง (Spacebar) ที่อาจเผลอติดมา
            if isinstance(p_data, dict):
                p_name = str(p_data.get("name", "")).strip()
            else:
                p_name = str(p_data).strip()
                
            my_name = str(self.player_name).strip()
            
            if not p_name: 
                continue # ถ้าไม่มีชื่อให้ข้ามไป

            # ถ้าตรงกับชื่อตัวเรา ให้ลงเก้าอี้ 3 (ล่างสุด) เสมอ
            if p_name == my_name:
                seat_idx = 3
            else:
                if other_idx < len(other_seats):
                    seat_idx = other_seats[other_idx]
                    other_idx += 1
                else:
                    continue # เก้าอี้เต็ม
            
            self.player_seat_map[p_name] = seat_idx
            
            color = "#60a5fa" if seat_idx == 3 else "white"
            self.bg_canvas.itemconfigure(
                self.player_objects[seat_idx]["name_id"], 
                text=p_name, 
                fill=color
            )

    def display_my_cards(self, data):
        """แสดงไพ่ลงบน Canvas โดยคำนวณตำแหน่งจากกรอบล่องหน"""
        all_data = data.get("all_players_data", {})
        
        if not hasattr(self, 'card_img_refs'): 
            self.card_img_refs = []

        # ล้างไพ่และคะแนนเก่าออกให้หมด
        self.bg_canvas.delete("cards_ui")
        self.bg_canvas.delete("score_ui")

        offsets = [
            {"dx": 0,    "dy": 85},   # 0
            {"dx": -210, "dy": -20},  # 1
            {"dx": -210, "dy": -100}, # 2
            {"dx": 0,    "dy": -220}, # 3
            {"dx": 210,  "dy": -100}, # 4
            {"dx": 210,  "dy": -20},  # 5
        ]

        for p_name, p_hand in all_data.items():
            if not hasattr(self, 'player_seat_map'): break
            seat_idx = self.player_seat_map.get(p_name)
            if seat_idx is None or seat_idx >= len(self.player_objects): continue

            cards = p_hand.get("cards", [])
            is_me = (p_name == self.player_name)
            
            if is_me:
                card_w, card_h = 75, 105  # ขนาดใหญ่สำหรับเรา
                spacing = 30              # ระยะห่างกว้างขึ้นนิดนึง
                self.my_current_score = p_hand.get("score", 0)
            else:
                card_w, card_h = 55, 78   # ขนาดเล็กลงสำหรับคนอื่น
                spacing = 22
            # --- คำนวณพิกัดกรอบล่องหน ---
            pos = self.seats[seat_idx]
            off = offsets[seat_idx]
            
            # จุดกึ่งกลางบนสุดของ "กรอบจำลอง"
            base_x = pos["x"] + off["dx"]
            base_y = pos["y"] + off["dy"]
            
            # จุดกึ่งกลางสำหรับวาดไพ่ (ขยับลงมา +50 เพราะจำลองว่ากรอบสูง 100)
            center_y = base_y + 50
            
            # หาจุด X เริ่มต้นให้ไพ่กระจายตัวสมมาตรอยู่ตรงกลางของ base_x
            start_x = base_x - ((len(cards) - 1) * spacing / 2)

            for i, c_name in enumerate(cards):
                try:
                    if is_me:
                        img_path = os.path.join(self.card_path, f"{c_name}.png")
                    else:
                        img_path = os.path.join(self.card_path, "Back Blue 1.png")
                        
                    pil_img = Image.open(img_path).resize((card_w, card_h), Image.Resampling.LANCZOS)
                    tk_img = ImageTk.PhotoImage(pil_img)
                    self.card_img_refs.append(tk_img)

                    # วาดไพ่ลงบน Canvas ตรงๆ 
                    self.bg_canvas.create_image(
                        start_x + (i * spacing), center_y, 
                        image=tk_img, tags="cards_ui"
                    )
                except Exception as e:
                    print(f"[ERROR] โหลดรูปไพ่ไม่ได้: {e}")

            # --- วาดกล่องคะแนน (เฉพาะตัวเรา) ---
            if is_me:
                score_text = f"🔥 POK {p_hand['score']} 🔥" if p_hand.get("is_pok") else f"{p_hand['score']} Points"
                score_bg = "#e11d48" if p_hand.get("is_pok") else "#f59e0b"
                
                # ขยับคะแนนลงมาให้อยู่ใต้กรอบล่องหน (base_y + ความสูงกรอบ 100 + ระยะห่าง 20)
                score_y = base_y + 130 # ขยับลงมาอีกนิดเพราะไพ่ใหญ่ขึ้น
                self.bg_canvas.create_rectangle(base_x-60, score_y-15, base_x+60, score_y+15, fill="#e11d48", tags="score_ui")
                self.bg_canvas.create_text(base_x, score_y, text=f"Points: {p_hand['score']}", fill="white", font=("Arial", 14, "bold"), tags="score_ui")

    def display_all_hands(self, all_data):
        """เปิดไพ่ของผู้เล่นทุกคนเมื่อจบเกมลงบน Canvas พร้อมโชว์คะแนน"""
        if not hasattr(self, 'card_img_refs'): 
            self.card_img_refs = []

        # 1. ล้างไพ่และคะแนนเก่าบน Canvas ออกให้หมด
        self.bg_canvas.delete("cards_ui")
        self.bg_canvas.delete("score_ui") 

        offsets = [
            {"dx": 0,    "dy": 85},   # 0
            {"dx": -210, "dy": -20},  # 1
            {"dx": -210, "dy": -100}, # 2
            {"dx": 0,    "dy": -220}, # 3
            {"dx": 210,  "dy": -100}, # 4
            {"dx": 210,  "dy": -20},  # 5
        ]

        for p_name, p_hand in all_data.items():
            if not hasattr(self, 'player_seat_map'): break
            seat_idx = self.player_seat_map.get(p_name)
            if seat_idx is None or seat_idx >= len(self.player_objects): continue

            cards = p_hand.get("cards", [])
            score = p_hand.get("score", 0)
            is_pok = p_hand.get("is_pok", False)

            pos = self.seats[seat_idx]
            off = offsets[seat_idx]
            
            # จุดอ้างอิงกลาง (base_x) และจุดกึ่งกลางไพ่ (center_y)
            base_x = pos["x"] + off["dx"]
            base_y = pos["y"] + off["dy"]
            center_y = base_y + 50
            
            is_me = (p_name == self.player_name)
            
       
            start_x = base_x - ((len(cards) - 1) * spacing / 2)
            if is_me:
                card_w, card_h = 75, 105
                spacing = 30
            else:
                card_w, card_h = 55, 78
                spacing = 22

            for i, c_name in enumerate(cards):
                try:
                    img_path = os.path.join(self.card_path, f"{c_name}.png")
                    pil_img = Image.open(img_path).resize((card_w, card_h), Image.Resampling.LANCZOS)
                    tk_img = ImageTk.PhotoImage(pil_img)
                    self.card_img_refs.append(tk_img)

                    self.bg_canvas.create_image(
                        start_x + (i * spacing), center_y, 
                        image=tk_img, tags="cards_ui"
                    )
                except Exception as e:
                    print(f"[ERROR] โหลดรูปไพ่ {c_name} ไม่ได้: {e}")

            # --- 3. วาดเลขคะแนน (Score Badge) ของทุกคน ---
            # กำหนดข้อความและสี (ป๊อก = แดง, ปกติ = ส้ม/เหลือง)
            score_text = f"🔥 POK {score} 🔥" if is_pok else f"{score} Points"
            score_bg = "#e11d48" if is_pok else "#334155" # สีแดงถ้าป๊อก สีเทาเข้มถ้าแต้มปกติ
            
            score_y = base_y + (130 if is_me else 110)
            score_bg = "#e11d48" if p_hand.get("is_pok") else "#334155"
            self.bg_canvas.create_rectangle(base_x-55, score_y-12, base_x+55, score_y+12, fill=score_bg, outline="white", tags="score_ui")
            self.bg_canvas.create_text(base_x, score_y, text=f"{p_hand['score']} Pts", fill="white", font=("Arial", 11, "bold"), tags="score_ui")

        print("[GAME] แสดงผลแพ้ชนะและเปิดไพ่เรียบร้อย")
    def update_turn_ui(self, msg):
        """รับข้อมูลจาก Server ว่าตอนนี้ตาใคร"""
        current_turn = msg.get("current_turn")
        
        # ล้าง UI นับเวลาของเก่าทิ้ง
        self.bg_canvas.delete("timer_ui")
        if self.timer_id:
            self.after_cancel(self.timer_id)
            self.timer_id = None

        if current_turn == self.player_name:
            # ตาเราเล่น! ปลดล็อคปุ่ม
            self.hit_btn.configure(state="normal")
            self.stand_btn.configure(state="normal")
            self.start_timer(10) # เริ่มนับถอยหลัง 10 วินาที
        else:
            # ตาคนอื่นเล่น บล็อคปุ่มเราไว้
            self.hit_btn.configure(state="disabled")
            self.stand_btn.configure(state="disabled")
            
            # โชว์ข้อความกลางจอว่ากำลังรอใคร
            self.bg_canvas.create_text(
                550, 700, text=f"รอ {current_turn} ตัดสินใจ...", 
                fill="#facc15", font=("Arial", 18, "bold"), tags="timer_ui"
            )

    def start_timer(self, time_left):
        self.bg_canvas.delete("timer_ui")
        
        if time_left > 0:
            # แสดงเวลานับถอยหลัง
            color = "#4ade80" if time_left > 3 else "#ef4444" # แดงถ้าน้อยกว่า 3 วิ
            self.bg_canvas.create_text(
                550, 700, text=f"ตาของคุณ! เหลือเวลา {time_left} วินาที", 
                fill=color, font=("Arial", 24, "bold"), tags="timer_ui"
            )
            self.timer_id = self.after(1000, lambda: self.start_timer(time_left - 1))
        else:
            # เวลาหมด! ทำ Auto-play
            self.bg_canvas.create_text(
                550, 700, text="หมดเวลา! ระบบกำลังตัดสินใจให้...", 
                fill="#f87171", font=("Arial", 24, "bold"), tags="timer_ui"
            )
            self.auto_play()

    def auto_play(self):
        """ถ้าแต้มไม่ถึง 5 จั่ว(hit) | ถ้า 5 ขึ้นไป อยู่(stand)"""
        if self.my_current_score < 5:
            print("[AUTO] แต้มไม่ถึง 5 -> ทำการจั่วไพ่")
            self.send_action("hit")
        else:
            print("[AUTO] แต้ม 5 ขึ้นไป -> ทำการอยู่")
            self.send_action("stand")
    def send_start_command(self):
        self.send_to_server({"action": "start_game", "room_id": self.room_id})
        if hasattr(self, 'start_btn'): self.start_btn.destroy()

    def send_action(self, act_type):
        self.send_to_server({"action": act_type, "room_id": self.room_id, "name": self.player_name})
        
        # กดเสร็จแล้ว บล็อคปุ่มตัวเองทันทีเพื่อป้องกันการกดเบิ้ล
        self.hit_btn.configure(state="disabled")
        self.stand_btn.configure(state="disabled")
        
        # หยุดการนับเวลา และลบข้อความจับเวลาออก
        if self.timer_id:
            self.after_cancel(self.timer_id)
            self.timer_id = None
        self.bg_canvas.delete("timer_ui")

if __name__ == "__main__":
    app = PokdengClient()
    app.mainloop()