"""
pokdeng_client.py  ป๊อกเด้งออนไลน์
====================================
3 หน้า: Login → Lobby → โต๊ะเกม
"""

import customtkinter as ctk
import socket, json, threading, os
from tkinter import messagebox, simpledialog

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except:
    PIL_OK = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── ค่าคงที่ ────────────────────────────────────────────────
SUIT_SYM = {"Clubs":"♣","Diamonds":"♦","Hearts":"♥","Spades":"♠","Diamond":"♦"}
SUIT_COL = {"Clubs":"#111","Diamonds":"#dc2626","Hearts":"#dc2626","Spades":"#111","Diamond":"#dc2626"}
RANK_LBL = {1:"A",11:"J",12:"Q",13:"K"}

SEAT_BG  = ["#7c3aed","#b45309","#0e7490","#1d4ed8","#065f46","#9d174d"]
SEAT_FG  = ["#ede9fe","#fef3c7","#cffafe","#dbeafe","#d1fae5","#fce7f3"]

# canvas ขนาด 760×480
W, H = 760, 480

# ตำแหน่ง 6 ที่นั่ง  (0=บน 1=ขวาบน 2=ขวาล่าง 3=ล่าง 4=ซ้ายล่าง 5=ซ้ายบน)
SEATS    = [(380,68),(650,158),(650,352),(380,415),(110,352),(110,158)]
CARD_OFF = [(0,72),(-100,5),(-100,-62),(0,-115),(100,-62),(100,5)]

CARD_DIR = os.path.join("assets","card")
_IMG = {}   # cache รูปไพ่

def _img(name, w, h):
    if not PIL_OK: return None
    k = (name,w,h)
    if k not in _IMG:
        p = os.path.join(CARD_DIR,name)
        if not os.path.exists(p): return None
        try:
            i = Image.open(p).resize((w,h),Image.Resampling.LANCZOS)
            _IMG[k] = ImageTk.PhotoImage(i)
        except: return None
    return _IMG[k]

def _card_file(card):
    for c in [card, card.replace("Diamonds","Diamond"), card.replace("Diamond ","Diamonds ")]:
        if os.path.exists(os.path.join(CARD_DIR,f"{c}.png")): return f"{c}.png"
    return f"{card}.png"

def draw_card(cv, x, y, card, face_up=True, w=62, h=88):
    """วาดไพ่ 1 ใบ คืน list ของ canvas IDs"""
    fname = "Back Blue 1.png" if not face_up else _card_file(card)
    img   = _img(fname, w, h)
    if img:
        iid = cv.create_image(x,y,image=img,anchor="center")
        if not hasattr(cv,"_refs"): cv._refs=[]
        cv._refs.append(img)
        return [iid]
    # fallback วาดรูปทรง
    if not face_up:
        return [cv.create_rectangle(x-w//2,y-h//2,x+w//2,y+h//2,fill="#1e40af",outline="#60a5fa",width=2)]
    suit, n = card.rsplit(" ",1); n=int(n)
    r = RANK_LBL.get(n,str(n)); s = SUIT_SYM.get(suit,"?"); col = SUIT_COL.get(suit,"#111")
    return [
        cv.create_rectangle(x-w//2,y-h//2,x+w//2,y+h//2,fill="white",outline="#cbd5e1",width=2),
        cv.create_text(x-w//2+5,y-h//2+9,text=r,font=("Arial",10,"bold"),fill=col,anchor="w"),
        cv.create_text(x,y,text=s,font=("Arial",20,"bold"),fill=col),
    ]

def draw_avatar(cv, x, y, name, i, host=False):
    """วาดวงอวตาร คืน list ของ canvas IDs"""
    bg=SEAT_BG[i%6]; fg=SEAT_FG[i%6]
    ab=(name[:3].upper() if len(name)>3 else name.upper()) if name else "??"
    sz=13 if len(ab)<=2 else 10
    ids=[]
    if host:
        ids.append(cv.create_oval(x-30,y-30,x+30,y+30,fill="",outline="#22c55e",width=4))
    ids+=[
        cv.create_oval(x-26,y-26,x+26,y+26,fill=bg,outline=""),
        cv.create_text(x,y,text=ab,font=("Arial",sz,"bold"),fill=fg),
    ]
    return ids


# ════════════════════════════════════════════════════════════
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("♠ Pokdeng Online"); self.resizable(False,False)

        # ─ state ─
        self.sock     = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.srv      = None
        self.me       = ""
        self.room_id  = ""
        self.password = ""
        self.is_host  = False
        self.balance  = 5000
        self.min_bet  = 100
        self.max_bet  = 1000
        self.seat_map = {}
        self.av_ids   = {}
        self.card_ids = []
        self.game_on  = False
        self.timer_id = None
        self.chat_msgs  = []
        self.unread     = 0
        self._chat_open = False

        self.page_login()

    # ── ช่วย ────────────────────────────────────────────────
    def clear(self):
        for w in self.winfo_children(): w.destroy()

    def send(self, d):
        if self.srv:
            try: self.sock.sendto(json.dumps(d).encode(),self.srv)
            except: pass

    def toast(self, msg, color="#f59e0b", ms=2500):
        t = ctk.CTkLabel(self,text=msg,font=("Arial",13,"bold"),
                         fg_color=color,text_color="white",corner_radius=10,padx=16,pady=8)
        t.place(relx=0.5,rely=0.07,anchor="center")
        self.after(ms, lambda: t.destroy() if t.winfo_exists() else None)

    # ════════════════════════════════════════════════════════
    # LOGIN
    # ════════════════════════════════════════════════════════
    def page_login(self):
        self.clear(); self.geometry("400x420"); self.configure(fg_color="#0f172a")
        f = ctk.CTkFrame(self,fg_color="#1e293b",corner_radius=18)
        f.pack(expand=True,padx=32,pady=32,fill="both")

        ctk.CTkLabel(f,text="♠",font=("Arial",50),text_color="#60a5fa").pack(pady=(22,0))
        ctk.CTkLabel(f,text="POKDENG ONLINE",font=("Arial",20,"bold")).pack()
        ctk.CTkLabel(f,text="เงินเริ่มต้น 5,000  ·  ป๊อก=8-9  ·  ตอง×5",
                     font=("Arial",10),text_color="#64748b").pack(pady=(4,18))

        self.ip_e = ctk.CTkEntry(f,placeholder_text="IP เซิร์ฟเวอร์ (127.0.0.1)",height=42,font=("Arial",13))
        self.ip_e.insert(0,"127.0.0.1"); self.ip_e.pack(padx=24,pady=4,fill="x")

        self.nm_e = ctk.CTkEntry(f,placeholder_text="ชื่อผู้เล่น",height=42,font=("Arial",13))
        self.nm_e.pack(padx=24,pady=4,fill="x")
        self.nm_e.bind("<Return>",lambda _:self.do_login())

        ctk.CTkButton(f,text="🎰  เข้าล็อบบี้",height=46,font=("Arial",14,"bold"),
                      fg_color="#2563eb",corner_radius=12,command=self.do_login).pack(padx=24,pady=16,fill="x")

    def do_login(self):
        ip = self.ip_e.get().strip() or "127.0.0.1"
        nm = self.nm_e.get().strip()
        if not nm: messagebox.showerror("ข้อผิดพลาด","กรอกชื่อก่อน",parent=self); return
        if len(nm)>12: messagebox.showerror("ข้อผิดพลาด","ชื่อยาวเกิน 12 ตัว",parent=self); return
        self.me=nm; self.srv=(ip,5005)
        self.send({"action":"enter_lobby","name":nm})
        threading.Thread(target=self.recv_loop,daemon=True).start()
        self.page_lobby()

    # ════════════════════════════════════════════════════════
    # LOBBY
    # ════════════════════════════════════════════════════════
    def page_lobby(self):
        self.clear(); self.geometry("820x520"); self.configure(fg_color="#0f172a")

        hdr = ctk.CTkFrame(self,fg_color="#1e293b",height=58,corner_radius=0)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr,text="♠  POKDENG LOBBY",font=("Arial",19,"bold"),text_color="#60a5fa").pack(side="left",padx=18)
        ctk.CTkLabel(hdr,text=f"👤 {self.me}  💰 {self.balance:,}",font=("Arial",12),text_color="#94a3b8").pack(side="left",padx=8)
        ctk.CTkButton(hdr,text="+ สร้างห้อง",fg_color="#16a34a",height=36,width=114,
                      font=("Arial",12,"bold"),command=self.create_dialog).pack(side="right",padx=16,pady=11)

        self.room_list = ctk.CTkScrollableFrame(self,fg_color="#0f172a",
            label_text="  🎮 ห้องที่เปิดอยู่",label_font=("Arial",13,"bold"),label_fg_color="#1e293b")
        self.room_list.pack(expand=True,fill="both",padx=14,pady=8)

    def refresh_rooms(self, rooms):
        if not hasattr(self,"room_list"): return
        for w in self.room_list.winfo_children(): w.destroy()
        if not rooms:
            ctk.CTkLabel(self.room_list,text="ยังไม่มีห้อง — กด 'สร้างห้อง'",
                         font=("Arial",13),text_color="#475569").pack(pady=40); return
        for r in rooms:
            row = ctk.CTkFrame(self.room_list,fg_color="#1e293b",corner_radius=12)
            row.pack(fill="x",pady=4,padx=6)
            live = r.get("status") in ("playing","ending")
            ctk.CTkLabel(row,
                text=f"🏠 {r['room_id']}  👑 {r['host']}  👥 {r['count']}/6  💰 {r.get('min_bet',100):,}–{r.get('max_bet',1000):,}",
                font=("Arial",12)).pack(side="left",padx=12,pady=11)
            ctk.CTkLabel(row,text="🔴 กำลังเล่น" if live else "🟢 รอผู้เล่น",
                         text_color="#f87171" if live else "#4ade80",font=("Arial",11)).pack(side="left")
            if not live:
                ctk.CTkButton(row,text="เข้าร่วม",width=88,height=32,fg_color="#2563eb",
                              command=lambda rid=r["room_id"]:self.do_join(rid)).pack(side="right",padx=12)

    def create_dialog(self):
        d=CreateDialog(self); self.wait_window(d)
        if d.result:
            self.send({"action":"create","name":self.me,**d.result})

    def do_join(self, rid):
        pwd = simpledialog.askstring("รหัสผ่าน",f"ห้อง {rid}\n(ว่างถ้าไม่มี):",parent=self) or ""
        self.send({"action":"join","room_id":rid,"name":self.me,"password":pwd})

    # ════════════════════════════════════════════════════════
    # โต๊ะเกม
    # ════════════════════════════════════════════════════════
    def page_table(self):
        self.clear(); self.geometry(f"{W}x{H+110}"); self.configure(fg_color="#0a0f1e")

        # bottom bar (pack ก่อน → canvas fill ส่วนที่เหลือ)
        self.bar = ctk.CTkFrame(self,fg_color="#111827",height=110,corner_radius=0)
        self.bar.pack(fill="x",side="bottom"); self.bar.pack_propagate(False)

        self.cv = ctk.CTkCanvas(self,width=W,height=H,bg="#0a0f1e",highlightthickness=0)
        self.cv.pack(fill="both",expand=True)

        self._draw_table()
        self._init_seats()
        self._draw_topbar()
        self._build_bar()
        self.card_ids=[]; self.game_on=False

    # ── วาดโต๊ะ ─────────────────────────────────────────────
    def _draw_table(self):
        cx,cy=W//2,H//2; rx,ry=W//2-22,H//2-22
        self.cv.create_oval(cx-rx,cy-ry,cx+rx,cy+ry,fill="",outline="#78350f",width=12)
        self.cv.create_oval(cx-rx+7,cy-ry+7,cx+rx-7,cy+ry-7,fill="#14532d",outline="#166534",width=3)
        self.cv.create_oval(cx-rx+20,cy-ry+20,cx+rx-20,cy+ry-20,fill="#166534",outline="#15803d",width=2)
        # สำรับไพ่กลางโต๊ะ
        self.deck_ids=[]
        for i in range(4,-1,-1):
            self.deck_ids.append(
                self.cv.create_rectangle(cx-22+i,cy-34-i,cx+22+i,cy+34-i,fill="#1e40af",outline="#60a5fa"))
        self.deck_lbl=self.cv.create_text(cx,cy+48,text="🃏 สำรับ",fill="#60a5fa",font=("Arial",10,"bold"))

    def _hide_deck(self):
        for i in self.deck_ids: self.cv.delete(i)
        self.cv.delete(self.deck_lbl)

    def _init_seats(self):
        self.seat_lbl=[]; self.av_ids={}
        for i,(sx,sy) in enumerate(SEATS):
            self.av_ids[i]=draw_avatar(self.cv,sx,sy,"",i)
            self.seat_lbl.append(self.cv.create_text(sx,sy+38,text="ว่าง",fill="#475569",font=("Arial",10,"bold")))

    def _draw_topbar(self):
        self.cv.create_rectangle(0,0,W,40,fill="#0f172a",outline="")
        self.bal_lbl=self.cv.create_text(12,20,text=f"💰 {self.balance:,}",
                                          fill="#4ade80",font=("Arial",12,"bold"),anchor="w")
        self.cv.create_text(W//2,20,text=f"ห้อง {self.room_id}  รหัส: {self.password or 'ไม่มี'}",
                             fill="#94a3b8",font=("Arial",10))
        self.cv.create_text(W-10,20,text="❌ ออก",fill="#f87171",font=("Arial",11,"bold"),
                             anchor="e",tags="exit_btn")
        self.cv.tag_bind("exit_btn","<Button-1>",lambda _:self.do_leave())
        self.status_lbl=self.cv.create_text(W//2,H//2,text="",fill="#facc15",font=("Arial",14,"bold"))

    # ── Bottom bar ───────────────────────────────────────────
    def _build_bar(self):
        # แถวเดียวตรงกลาง
        row=ctk.CTkFrame(self.bar,fg_color="transparent")
        row.place(relx=0.5,rely=0.5,anchor="center")

        # ปุ่มแชท
        self.chat_btn=ctk.CTkButton(row,text="💬",width=50,height=50,font=("Arial",20),
                                     corner_radius=25,fg_color="#1e293b",hover_color="#334155",
                                     command=self.toggle_chat)
        self.chat_btn.pack(side="left",padx=6)
        # badge ข้อความใหม่
        self.badge=ctk.CTkLabel(self.bar,text="",font=("Arial",9,"bold"),
                                 fg_color="#e11d48",text_color="white",corner_radius=8,width=18,height=18)

        ctk.CTkLabel(row,text="│",text_color="#334155",font=("Arial",24)).pack(side="left",padx=6)

        # จั่ว / อยู่
        self.hit_btn=ctk.CTkButton(row,text="🃏 จั่ว",width=135,height=50,
                                    font=("Arial",15,"bold"),fg_color="#16a34a",corner_radius=12,
                                    state="disabled",command=lambda:self.act("hit"))
        self.hit_btn.pack(side="left",padx=6)

        self.stand_btn=ctk.CTkButton(row,text="✋ อยู่",width=135,height=50,
                                      font=("Arial",15,"bold"),fg_color="#1d4ed8",corner_radius=12,
                                      state="disabled",command=lambda:self.act("stand"))
        self.stand_btn.pack(side="left",padx=6)

        ctk.CTkLabel(row,text="│",text_color="#334155",font=("Arial",24)).pack(side="left",padx=6)

        # กล่องฝั่งขวา (host=ปุ่มเริ่ม, ไม่ใช่=วางเดิมพัน)
        self.extra=ctk.CTkFrame(row,fg_color="transparent"); self.extra.pack(side="left",padx=6)
        if self.is_host: self._make_host_ui()
        else:            self._make_bet_ui()

    def _clear_extra(self):
        for w in self.extra.winfo_children(): w.destroy()

    def _make_host_ui(self):
        self._clear_extra()
        self.start_btn=ctk.CTkButton(self.extra,text="🚀 เริ่มเกม",
                                      fg_color="#e11d48",hover_color="#be123c",
                                      width=175,height=50,font=("Arial",15,"bold"),
                                      corner_radius=12,command=self._start)
        self.start_btn.pack()

    def _make_bet_ui(self):
        self._clear_extra()
        r=ctk.CTkFrame(self.extra,fg_color="transparent"); r.pack()
        self.bet_e=ctk.CTkEntry(r,width=95,height=50,font=("Arial",14,"bold"),
                                 placeholder_text=str(self.min_bet))
        self.bet_e.pack(side="left",padx=4)
        self.bet_e.bind("<Return>",lambda _:self._bet())
        ctk.CTkButton(r,text="✅ วาง",fg_color="#16a34a",width=120,height=50,
                      font=("Arial",14,"bold"),corner_radius=12,command=self._bet).pack(side="left",padx=4)
        ctk.CTkLabel(self.extra,text=f"เดิมพัน {self.min_bet:,}–{self.max_bet:,} บาท",
                     font=("Arial",10),text_color="#64748b").pack()

    def _start(self):
        self.start_btn.configure(state="disabled",text="⏳ กำลังเริ่ม...")
        self.send({"action":"start_game","room_id":self.room_id})

    def _reset_start(self):
        if hasattr(self,"start_btn") and self.start_btn.winfo_exists():
            self.start_btn.configure(state="normal",text="🚀 เริ่มเกม")

    def _bet(self):
        try: b=int(self.bet_e.get())
        except: self.toast("กรอกตัวเลข","#e11d48"); return
        if not (self.min_bet<=b<=self.max_bet):
            self.toast(f"เดิมพัน {self.min_bet:,}–{self.max_bet:,}","#e11d48"); return
        if b>self.balance:
            self.toast("เงินไม่พอ 💸","#e11d48"); return
        self.send({"action":"place_bet","room_id":self.room_id,"bet":b})

    # ── ที่นั่ง ──────────────────────────────────────────────
    def update_seats(self, players, host=""):
        if not hasattr(self,"cv"): return
        for i in range(6):
            for id_ in self.av_ids.get(i,[]): self.cv.delete(id_)
            self.av_ids[i]=[]
            self.cv.itemconfigure(self.seat_lbl[i],text="ว่าง",fill="#475569")
        self.cv.delete("host_tag")
        self.seat_map={}
        others=[0,1,2,4,5]; oi=0
        for p in players:
            nm=(p.get("name","").strip() if isinstance(p,dict) else str(p))
            if not nm: continue
            bal=p.get("balance",5000); bet=p.get("bet",0); ih=(nm==host)
            seat=3 if nm==self.me else (others[oi] if oi<len(others) else None)
            if seat is None: continue
            if nm!=self.me: oi+=1
            self.seat_map[nm]=seat
            sx,sy=SEATS[seat]
            self.av_ids[seat]=draw_avatar(self.cv,sx,sy,nm,seat,host=ih)
            if ih:  # badge เจ้ามือเล็กๆ เหนือวง
                self.cv.create_rectangle(sx-28,sy-44,sx+28,sy-28,fill="#16a34a",outline="#22c55e",tags="host_tag")
                self.cv.create_text(sx,sy-36,text="♛ เจ้ามือ",fill="white",font=("Arial",8,"bold"),tags="host_tag")
            money=f"\n🎰{bet:,}" if bet else f"\n💰{bal:,}"
            col="#60a5fa" if nm==self.me else ("#fbbf24" if ih else "white")
            self.cv.itemconfigure(self.seat_lbl[seat],text=nm+money,fill=col)
            if nm==self.me:
                self.balance=bal
                self.cv.itemconfigure(self.bal_lbl,text=f"💰 {bal:,}")

    # ── ไพ่ ──────────────────────────────────────────────────
    def clear_cards(self):
        for i in self.card_ids: self.cv.delete(i)
        self.card_ids=[]
        self.cv.delete("score_tag","result_tag")
        if hasattr(self.cv,"_refs"): self.cv._refs.clear()

    def render_hands(self, data, reveal=False):
        self.clear_cards()
        for nm,hand in data.items():
            seat=self.seat_map.get(nm)
            if seat is None: continue
            sx,sy=SEATS[seat]; ox,oy=CARD_OFF[seat]
            cards=hand.get("cards",[]); is_me=(nm==self.me)
            cw,ch,sp=(62,88,25) if is_me else (44,64,17)
            fu=is_me or reveal
            n=len(cards); bx=sx+ox-(n-1)*sp/2
            for i,c in enumerate(cards):
                self.card_ids.extend(draw_card(self.cv,int(bx+i*sp),int(sy+oy+ch//2),c,face_up=fu,w=cw,h=ch))
            if fu:
                sc=hand.get("score",0); pk=hand.get("is_pok",False)
                mt=hand.get("multiplier",1); dn=hand.get("deng_name","")
                lx=int(bx+(n-1)*sp); ly=int(sy+oy+ch+14)
                txt=(f"🔥ป๊อก{sc}" if pk else f"{sc}แต้ม")+(f"·{dn}" if mt>1 else "")
                bw=max(58,len(txt)*7); bc="#e11d48" if pk else ("#a855f7" if mt>1 else "#334155")
                self.card_ids+=[
                    self.cv.create_rectangle(lx-bw//2,ly-11,lx+bw//2,ly+11,fill=bc,outline="white",tags="score_tag"),
                    self.cv.create_text(lx,ly,text=txt,fill="white",font=("Arial",9,"bold"),tags="score_tag"),
                ]

    # ── เทิร์น ───────────────────────────────────────────────
    def act(self, a):
        self.hit_btn.configure(state="disabled"); self.stand_btn.configure(state="disabled")
        self._stop_timer()
        self.send({"action":a,"room_id":self.room_id,"name":self.me})

    def _stop_timer(self):
        if self.timer_id: self.after_cancel(self.timer_id); self.timer_id=None
        if hasattr(self,"cv"): self.cv.delete("timer_tag")

    def on_turn(self, cur):
        self._stop_timer()
        if not hasattr(self,"cv"): return
        self.cv.itemconfigure(self.status_lbl,text="")
        if cur==self.me:
            self.hit_btn.configure(state="normal"); self.stand_btn.configure(state="normal")
            self.toast("🎴 ถึงตาคุณ! จั่วหรืออยู่?","#1d4ed8",1500)
            self._tick(15)
        else:
            self.hit_btn.configure(state="disabled"); self.stand_btn.configure(state="disabled")
            self.cv.itemconfigure(self.status_lbl,text=f"⏳ ตา {cur} กำลังตัดสินใจ...")

    def _tick(self, t):
        if not hasattr(self,"cv"): return
        self.cv.delete("timer_tag")
        col="#4ade80" if t>5 else ("#f59e0b" if t>2 else "#ef4444")
        self.cv.create_text(W//2,H-32,text=f"⏱ เหลือ {t} วิ",
                             fill=col,font=("Arial",15,"bold"),tags="timer_tag")
        if t>0: self.timer_id=self.after(1000,lambda:self._tick(t-1))
        else:
            self.cv.itemconfigure(self.status_lbl,text="⏰ หมดเวลา")
            self.after(300,lambda:self.act("stand"))

    # ── ผลเกม ────────────────────────────────────────────────
    def show_result(self, data, results):
        self.render_hands(data,reveal=True)
        self.game_on=False; self._stop_timer()
        r=results.get(self.me,{}); oc=r.get("outcome","draw")
        chg=r.get("change",0); bal=r.get("balance",self.balance)
        if   oc=="win":  col="#16a34a"; txt=f"🎉 ชนะ  +{chg:,} บาท"
        elif oc=="lose": col="#e11d48"; txt=f"😢 แพ้  -{abs(chg):,} บาท"
        elif oc=="host": col="#f59e0b"; txt=f"👑 เจ้ามือ  {'+' if chg>=0 else ''}{chg:,} บาท"
        else:            col="#94a3b8"; txt="🤝 เสมอ"

        # วาดกล่องผลบน canvas — ขนาดเล็กพอดี ไม่บังหน้าจอ
        cx,cy=W//2,H//2; bw=300; bh=82
        self.cv.delete("result_tag")
        ids=[
            self.cv.create_rectangle(cx-bw//2-3,cy-bh//2-3,cx+bw//2+3,cy+bh//2+3,
                                      fill=col,tags="result_tag"),
            self.cv.create_rectangle(cx-bw//2,cy-bh//2,cx+bw//2,cy+bh//2,
                                      fill="#0f172a",tags="result_tag"),
            self.cv.create_text(cx,cy-14,text=txt,fill=col,
                                 font=("Arial",17,"bold"),tags="result_tag"),
            self.cv.create_text(cx,cy+12,text=f"💰 เงินคงเหลือ {bal:,} บาท",
                                 fill="white",font=("Arial",11),tags="result_tag"),
            self.cv.create_text(cx,cy+30,
                                 text=("กด 'เริ่มเกม' รอบต่อไป" if self.is_host else "วางเดิมพันรอบต่อไป"),
                                 fill="#64748b",font=("Arial",9),tags="result_tag"),
        ]
        self.card_ids.extend(ids)
        self.balance=bal; self.cv.itemconfigure(self.bal_lbl,text=f"💰 {bal:,}")
        self.toast(txt,col,3000)
        if self.is_host: self._reset_start()
        else: self._make_bet_ui()

    # ── เกมถูกยกเลิก (เจ้ามือออก) ──────────────────────────
    def on_aborted(self, msg):
        self.game_on=False; self._stop_timer()
        self.hit_btn.configure(state="disabled"); self.stand_btn.configure(state="disabled")
        self.clear_cards()
        self.toast(msg,"#f59e0b",5000)
        if not self.is_host: self._make_bet_ui()

    # ── Chat ────────────────────────────────────────────────
    def toggle_chat(self):
        if self._chat_open: self._close_chat()
        else: self._open_chat()

    def _open_chat(self):
        self._chat_open=True; self.unread=0
        self.badge.place_forget(); self.chat_btn.configure(fg_color="#2563eb")
        cf=ctk.CTkFrame(self.cv,fg_color="#111827",corner_radius=12,width=265,height=285)
        self._cwin=self.cv.create_window(4,H-4,window=cf,anchor="sw"); self._cf=cf

        hdr=ctk.CTkFrame(cf,fg_color="#1e293b",height=28,corner_radius=0)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr,text="💬 แชท",font=("Arial",10,"bold"),text_color="#94a3b8").pack(side="left",padx=8)
        ctk.CTkButton(hdr,text="✕",width=24,height=20,font=("Arial",9),
                      fg_color="transparent",hover_color="#374151",command=self._close_chat).pack(side="right",padx=3)

        self._inner=ctk.CTkScrollableFrame(cf,fg_color="#111827",width=245,height=216)
        self._inner.pack(fill="both",expand=True,padx=2,pady=2)
        saved=self.chat_msgs[:]; self.chat_msgs=[]
        for s,m,me in saved: self._bubble(s,m,me)

        ir=ctk.CTkFrame(cf,fg_color="#1e293b",height=38); ir.pack(fill="x"); ir.pack_propagate(False)
        self._ce=ctk.CTkEntry(ir,height=26,font=("Arial",10),placeholder_text="พิมพ์...",
                               fg_color="#374151",border_width=0,text_color="white")
        self._ce.pack(side="left",fill="x",expand=True,padx=6)
        self._ce.bind("<Return>",self._send_chat); self._ce.focus_set()
        ctk.CTkButton(ir,text="➤",width=28,height=24,font=("Arial",10),fg_color="#2563eb",
                      command=self._send_chat).pack(side="left",padx=(0,4))

    def _close_chat(self):
        self._chat_open=False; self.chat_btn.configure(fg_color="#1e293b")
        for attr in ("_cwin","_cf"):
            obj=getattr(self,attr,None)
            if obj:
                try: (self.cv.delete if attr=="_cwin" else obj.destroy)(obj if attr=="_cwin" else None)
                except: pass
        try: self._cf.destroy()
        except: pass

    def _send_chat(self,_=None):
        if not hasattr(self,"_ce"): return
        msg=self._ce.get().strip()
        if not msg: return
        self.send({"action":"chat","room_id":self.room_id,"name":self.me,"message":msg})
        self._ce.delete(0,"end"); self._bubble(self.me,msg,True)

    def add_chat(self, sender, msg):
        if sender==self.me: return
        self._bubble(sender,msg,False)
        if not self._chat_open:
            self.unread+=1
            self.badge.configure(text=str(self.unread if self.unread<10 else "9+"))
            self.badge.place(in_=self.chat_btn,relx=0.82,rely=0.12,anchor="center")

    def _bubble(self, sender, msg, is_me=False):
        self.chat_msgs.append((sender,msg,is_me))
        if len(self.chat_msgs)>50: self.chat_msgs.pop(0)
        if not hasattr(self,"_inner"): return
        outer=ctk.CTkFrame(self._inner,fg_color="transparent"); outer.pack(fill="x",pady=2,padx=4)
        bub=ctk.CTkFrame(outer,fg_color="#1d4ed8" if is_me else "#1e293b",corner_radius=8)
        if is_me:
            bub.pack(side="right")
            ctk.CTkLabel(bub,text=msg,font=("Arial",10),text_color="white",wraplength=150,justify="right").pack(padx=7,pady=4)
        else:
            bub.pack(side="left")
            ctk.CTkLabel(bub,text=sender,font=("Arial",8,"bold"),text_color="#94a3b8").pack(padx=7,pady=(3,0),anchor="w")
            ctk.CTkLabel(bub,text=msg,font=("Arial",10),text_color="white",wraplength=150).pack(padx=7,pady=(0,4))
        self.after(60,lambda:self._inner._parent_canvas.yview_moveto(1.0))

    # ── ออกห้อง ──────────────────────────────────────────────
    def do_leave(self):
        if self.room_id:
            self.send({"action":"leave","room_id":self.room_id,"name":self.me})
        self.room_id=""; self.is_host=False; self.password=""; self._stop_timer()
        self.send({"action":"enter_lobby","name":self.me})
        self.page_lobby()

    # ════════════════════════════════════════════════════════
    # รับข้อมูลจาก Server (thread แยก)
    # ════════════════════════════════════════════════════════
    def recv_loop(self):
        while True:
            try:
                raw,_=self.sock.recvfrom(16384)
                msg=json.loads(raw.decode()); st=msg.get("status","")

                if   st=="lobby_update":  self.after(0,lambda m=msg:self.refresh_rooms(m.get("rooms",[])))
                elif st=="name_taken":    self.after(0,lambda m=msg:[messagebox.showerror("ชื่อซ้ำ",m.get("message",""),parent=self),self.page_login()])
                elif st=="error":
                    e=msg.get("message","")
                    self.after(0,lambda e=e:messagebox.showerror("แจ้งเตือน",e,parent=self))
                    if self.is_host: self.after(0,self._reset_start)

                elif st in("created","joined"):
                    self.room_id=msg["room_id"]; self.is_host=msg["is_host"]
                    self.min_bet=msg.get("min_bet",100); self.max_bet=msg.get("max_bet",1000)
                    self.password=msg.get("password","")
                    self.after(0,self.page_table)
                    self.after(400,lambda:self.send({"action":"get_room_update","room_id":self.room_id}))

                elif st=="room_update":
                    pl=msg.get("players",[]); hn=msg.get("host_name","")
                    if hn==self.me and not self.is_host: self.is_host=True
                    self.after(0,lambda p=pl,h=hn:self.update_seats(p,h))

                elif st=="bet_confirmed":
                    b=msg.get("bet",0); self.after(0,lambda b=b:self.toast(f"✅ วาง {b:,} บาท","#16a34a"))
                    self.after(0,self._clear_extra)  # ซ่อน bet ui

                elif st=="game_started":
                    ah=msg.get("all_players_data",{})
                    if not self.game_on:
                        self.game_on=True
                        self.after(0,lambda d=ah:(self._hide_deck(),self.render_hands(d)))
                    else: self.after(0,lambda d=ah:self.render_hands(d))

                elif st=="pok_alert":
                    poks=msg.get("pok_players",[]); hp=msg.get("host_pok",False)
                    t="  ".join(f"🃏{p} ป๊อก!" for p in poks)+("\n💥เจ้ามือป๊อก!" if hp else "")
                    self.after(0,lambda t=t:self.toast(t,"#e11d48",4000))

                elif st=="turn_update":  self.after(0,lambda m=msg:self.on_turn(m.get("current_turn","")))
                elif st=="game_over":
                    ah=msg.get("all_players_data",{}); rs=msg.get("results",{})
                    self.game_on=False
                    self.after(0,lambda d=ah,r=rs:self.show_result(d,r))

                elif st=="game_aborted": self.after(0,lambda m=msg:self.on_aborted(m.get("message","⚠️ เกมถูกยกเลิก")))

                elif st=="kicked":
                    km=msg.get("message","เงินหมด!"); self.balance=0; self.room_id=""
                    self.after(0,lambda m=km:[messagebox.showinfo("💸 เงินหมด!",m,parent=self),
                                              self.send({"action":"enter_lobby","name":self.me}),self.page_lobby()])

                elif st=="chat":        self.after(0,lambda m=msg:self.add_chat(m.get("sender","?"),m.get("message","")))
                elif st=="player_left": self.after(0,lambda m=msg:self.toast(m.get("message",""),"#f59e0b"))
                elif st=="you_are_host":
                    self.is_host=True
                    self.after(0,lambda m=msg:self.toast(m.get("message",""),"#fbbf24",4000))
                    def become_host():
                        self._clear_extra(); self.start_btn=None; self._make_host_ui()
                    self.after(300,become_host)

            except Exception:
                import traceback; traceback.print_exc(); break


# ── Dialog สร้างห้อง ─────────────────────────────────────────
class CreateDialog(ctk.CTkToplevel):
    def __init__(self,parent):
        super().__init__(parent)
        self.title("สร้างห้องใหม่"); self.geometry("500x400")
        self.resizable(False,False); self.result=None
        self.grab_set(); self.configure(fg_color="#0f172a"); self.lift(); self.focus_force()

        f=ctk.CTkFrame(self,fg_color="transparent"); f.pack(fill="both",expand=True,padx=24,pady=18)
        ctk.CTkLabel(f,text="🏠 สร้างห้องใหม่",font=("Arial",16,"bold"),text_color="#60a5fa").pack(pady=(0,14))

        def row(lbl,default="",ph=""):
            ctk.CTkLabel(f,text=lbl,font=("Arial",11),text_color="#94a3b8",anchor="w").pack(fill="x",pady=(8,2))
            e=ctk.CTkEntry(f,height=40,font=("Arial",13),placeholder_text=ph)
            if default: e.insert(0,default)
            e.pack(fill="x"); return e

        self.pwd=row("🔒 รหัสผ่าน",ph="ว่างไว้ถ้าไม่ต้องการ")
        self.mn =row("💸 เดิมพันขั้นต่ำ",default="100")
        self.mx =row("💰 เดิมพันสูงสุด", default="1000")

        ctk.CTkButton(f,text="✅ สร้างห้อง",fg_color="#16a34a",height=44,
                      font=("Arial",14,"bold"),corner_radius=12,command=self.confirm).pack(fill="x",pady=16)

    def confirm(self):
        try:
            mn=int(self.mn.get()); mx=int(self.mx.get()); assert mn>0 and mx>=mn
        except: messagebox.showwarning("ผิดพลาด","ตัวเลขไม่ถูกต้อง",parent=self); return
        self.result={"password":self.pwd.get().strip(),"min_bet":mn,"max_bet":mx}
        self.destroy()


if __name__=="__main__":
    App().mainloop()