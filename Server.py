import socket
import json
import random
import time
class PokdengServer:
    def __init__(self, host='0.0.0.0', port=5005):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.lobby_clients = set()
        self.rooms = {}

    def get_card_deck(self):
        suits = ['Clubs', 'Diamond', 'Hearts', 'Spades']
        deck = [f"{s} {n}" for s in suits for n in range(1, 14)]
        random.shuffle(deck)
        return deck

    def evaluate_hand(self, cards):
        values = []
        suits = []
        for c in cards:
            s, v = c.split(' ')
            val = int(v)
            suits.append(s)
            values.append(0 if val >= 10 else (1 if val == 1 else val))
        
        score = sum(values) % 10
        is_pok = score >= 8 and len(cards) == 2
        is_deng = False
        if len(cards) == 2:
            if (cards[0].split(' ')[1] == cards[1].split(' ')[1]) or (suits[0] == suits[1]):
                is_deng = True
        return score, is_pok, is_deng

    # --- ฟังก์ชันใหม่: ส่งหารายชื่อห้องให้ทุกคนใน Lobby ---
    def broadcast_lobby_update(self):
        room_list = []
        for r_id, r_data in self.rooms.items():
            room_list.append({
                "room_id": r_id,
                "host": r_data["host_name"],
                "count": len(r_data["players"])
            })
        
        msg = json.dumps({"status": "lobby_update", "rooms": room_list}).encode()
        for client_addr in list(self.lobby_clients):
            try:
                self.sock.sendto(msg, client_addr)
            except:
                self.lobby_clients.remove(client_addr)

    # --- ฟังก์ชันใหม่: ส่งหาทุกคนที่อยู่ในห้องเล่นเกมนั้นๆ ---
    def broadcast_to_room(self, room_id, message_dict):
        room = self.rooms.get(room_id)
        if room:
            msg_bytes = json.dumps(message_dict).encode()
            for p_info in room["players"].values():
                self.sock.sendto(msg_bytes, p_info["addr_obj"])
        
    def broadcast_player_list(self, room_id):
        room = self.rooms.get(room_id)
        if room:
            players_in_room = []
            for p_info in room["players"].values():
                players_in_room.append({
                    "name": p_info["name"],
                    "balance": p_info.get("balance", 5000) # ดึงยอดเงินจาก Server
                })
            
            # ส่งสถานะ "room_update" ไปหาทุกคน
            self.broadcast_to_room(room_id, {
                "status": "room_update", 
                "players": players_in_room
            })

    def get_all_hands_data(self, room):
        """ตัวช่วยดึงข้อมูลไพ่ของทุกคนในห้องเพื่อเตรียมส่ง"""
        all_hands = {}
        for p_addr, p_info in room["players"].items():
            cards = p_info["cards"]
            score, is_pok, is_deng = self.evaluate_hand(cards)
            all_hands[p_info["name"]] = {
                "cards": cards,
                "score": score,
                "is_pok": is_pok,
                "is_deng": is_deng,
                "balance": p_info.get("balance", 5000)
            }
        return all_hands

    def send_turn_update(self, room_id):
        """เช็คว่าตาใคร แล้วประกาศบอกทุกคน หรือจบเกมถ้าเล่นครบแล้ว"""
        room = self.rooms.get(room_id)
        if not room: return
        
        idx = room.get("current_turn_idx", 0)
        turn_order = room.get("turn_order", [])
        
        if idx < len(turn_order):
            # ยังมีคนไม่ได้เล่น แจ้งเทิร์นคนถัดไป
            current_addr = turn_order[idx]
            current_name = room["players"][current_addr]["name"]
            self.broadcast_to_room(room_id, {
                "status": "turn_update",
                "current_turn": current_name
            })
        else:
            # เล่นครบทุกคนแล้ว -> ส่งคำสั่งโชว์ไพ่ทั้งโต๊ะ
            all_hands = self.get_all_hands_data(room)
            self.broadcast_to_room(room_id, {
                "status": "show_all_cards",
                "all_players_data": all_hands
            })
    def run(self):
        print("Server Pokdeng is Online...")
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                msg = json.loads(data.decode())
                action = msg.get("action")
                addr_str = str(addr)

                if action == "enter_lobby":
                    self.lobby_clients.add(addr) 
                    self.broadcast_lobby_update() 
                    continue

                if action == "create":
                    # 1. สุ่ม ID ห้อง
                    room_id = str(random.randint(100000, 999999))
                    
                    # 2. รับรหัสผ่านจาก Client (ถ้าไม่มีให้เป็นค่าว่าง)
                    room_password = msg.get("password", "")

                    # 3. สร้างข้อมูลห้อง
                    self.rooms[room_id] = {
                        "players": {
                            addr_str: {
                                "name": msg['name'], 
                                "cards": [], 
                                "balance": 5000, 
                                "addr_obj": addr
                            }
                        },
                        "host_name": msg['name'],
                        "password": room_password,  # <--- เพิ่มการเก็บรหัสผ่านตรงนี้
                        "deck": self.get_card_deck()
                    }

                    # 4. ย้ายผู้เล่นออกจาก Lobby List
                    if addr in self.lobby_clients:
                        self.lobby_clients.remove(addr)

                    # 5. ส่งสถานะ "created" กลับไปบอกผู้สร้างว่าเป็นเจ้ามือ
                    self.sock.sendto(json.dumps({
                        "status": "created", 
                        "room_id": room_id, 
                        "is_host": True
                    }).encode(), addr)

                    # 6. อัปเดตรายชื่อห้องให้ทุกคนใน Lobby เห็น
                    self.broadcast_lobby_update()

                elif action == "join":
                    r_id = msg.get("room_id")
                    entered_password = msg.get("password", "")  

                    if r_id in self.rooms:
                        room = self.rooms[r_id]

                        if room.get("password") != entered_password:
                            self.sock.sendto(json.dumps({
                                "status": "error", 
                                "message": "รหัสผ่านไม่ถูกต้อง!"
                            }).encode(), addr)
                            continue 

                        if len(room["players"]) >= 6:
                            self.sock.sendto(json.dumps({
                                "status": "error", 
                                "message": "Room is full (Max 6)"
                            }).encode(), addr)
                            continue
                        
                        # เพิ่มผู้เล่นใหม่เข้าห้อง
                        room["players"][addr_str] = {
                            "name": msg['name'], 
                            "cards": [], 
                            "balance": 5000, 
                            "addr_obj": addr
                        }
                        
                        if addr in self.lobby_clients:
                            self.lobby_clients.remove(addr)

                        # ส่งบอกคนใหม่ว่า "เข้าห้องสำเร็จแล้ว"
                        self.sock.sendto(json.dumps({"status": "joined", "room_id": r_id, "is_host": False}).encode(), addr)
                        
                        # ==========================================
                        # 🛠️ ส่วนที่แก้ไข: สร้างรายชื่อล่าสุดแล้วส่งให้ทุกคนในห้อง
                        # ==========================================
                        # 1. จัดโครงสร้างรายชื่อผู้เล่นปัจจุบันทั้งหมดในห้อง
                        players_list = [{"name": p["name"]} for p in room["players"].values()]
                        
                        # 2. ส่งข้อมูลไปให้ทุกคนในห้องอัปเดตหน้าจอพร้อมกัน
                        self.broadcast_to_room(r_id, {
                            "status": "room_update",
                            "players": players_list
                        })
                        # ==========================================

                        self.broadcast_to_room(r_id, {"status": "player_joined", "message": f"{msg['name']} joined!"})
                        self.broadcast_lobby_update()

                    else:
                        self.sock.sendto(json.dumps({"status": "error", "message": "Room not found"}).encode(), addr)
                elif action == "get_room_update":
                    r_id = msg.get("room_id")
                    room = self.rooms.get(r_id)
                    if room:
                        players_list = [{"name": p["name"]} for p in room["players"].values()]
                        self.sock.sendto(json.dumps({
                            "status": "room_update",
                            "players": players_list
                        }).encode(), addr)
                elif action == "start_game":
                    r_id = msg.get("room_id")
                    room = self.rooms.get(r_id)
                    if room:
                        room["deck"] = self.get_card_deck()
                        
                        # 1. แจกไพ่คนละ 2 ใบ
                        for p_addr_str, p_info in room["players"].items():
                            c1, c2 = room["deck"].pop(), room["deck"].pop()
                            p_info["cards"] = [c1, c2]
                        
                        # 2. ส่งข้อมูลไพ่ไปให้ทุกคน (ให้ UI ฝั่ง Client วาดไพ่เริ่มต้น)
                        all_hands = self.get_all_hands_data(room)
                        self.broadcast_to_room(r_id, {
                            "status": "game_started",
                            "all_players_data": all_hands
                        })
                        time.sleep(0.1)
                        # 3. สร้างคิวผู้เล่น และเริ่มเทิร์นแรก
                        room["turn_order"] = list(room["players"].keys())
                        room["current_turn_idx"] = 0
                        self.send_turn_update(r_id)
                elif action in ["hit", "stand"]:
                    r_id = msg.get("room_id")
                    room = self.rooms.get(r_id)
                    if room:
                        # ป้องกันคนอื่นเนียนกด เช็คว่าตอนนี้ใช่ตาของคนที่ส่งมาไหม?
                        current_addr = room["turn_order"][room["current_turn_idx"]]
                        
                        if str(addr) == current_addr:
                            if action == "hit":
                                # แจกเพิ่ม 1 ใบ
                                new_card = room["deck"].pop()
                                room["players"][current_addr]["cards"].append(new_card)
                                
                                # ส่งอัปเดตไพ่ในมือให้หน้าจอ (ใช้ game_started Client จะได้อัปเดตภาพไพ่)
                                all_hands = self.get_all_hands_data(room)
                                self.broadcast_to_room(r_id, {
                                    "status": "game_started", 
                                    "all_players_data": all_hands
                                })
                                time.sleep(0.1)
                            # จบตาตัวเอง เลื่อนไปเทิร์นคนถัดไป
                            room["current_turn_idx"] += 1
                            self.send_turn_update(r_id)
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    PokdengServer().run()