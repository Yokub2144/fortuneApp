"""
pokdeng_server.py  ป๊อกเด้งออนไลน์
=====================================
กติกา: แต้ม 0-9 | ป๊อก=2ใบ 8-9แต้ม | 2เด้ง×2 | ตอง×5
"""

import socket, json, random, time, threading

PORT = 5005
START = 5000  # เงินเริ่มต้น


class Server:
    def __init__(self):
        self.sock   = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", PORT))
        self.lobby  = {}  # addr → ชื่อ
        self.rooms  = {}  # rid  → ข้อมูลห้อง
        self.p2room = {}  # astr → rid
        print(f"[SERVER] port {PORT} ✓")

    # ── ไพ่ ──────────────────────────────────────────────────
    def new_deck(self):
        deck = [f"{s} {n}" for s in ["Clubs","Diamond","Hearts","Spades"] for n in range(1,14)]
        for _ in range(3):
            for i in range(len(deck)-1,0,-1):
                j=random.randint(0,i); deck[i],deck[j]=deck[j],deck[i]
        return deck

    def score(self, cards):
        def v(c): n=int(c.split()[1]); return 0 if n>=10 else (1 if n==1 else n)
        def s(c): return c.split()[0]
        def n(c): return int(c.split()[1])
        pts = sum(v(c) for c in cards) % 10
        is_pok = pts>=8 and len(cards)==2
        mult=1; dname=""
        if len(cards)==2:
            if s(cards[0])==s(cards[1]) and n(cards[0])==n(cards[1]): mult,dname=2,"2เด้ง(สูทเลขเดียว)"
            elif s(cards[0])==s(cards[1]) or n(cards[0])==n(cards[1]): mult,dname=2,"2เด้ง"
        if len(cards)==3:
            suits=[s(c) for c in cards]; nums=sorted(n(c) for c in cards)
            if   len(set(nums))==1:                       mult,dname=5,"ตอง(×5)"
            elif len(set(suits))==1:                      mult,dname=3,"3เด้ง(×3)"
            elif all(n(c)>=10 for c in cards):            mult,dname=3,"สามเหลือง(×3)"
            elif nums[2]-nums[0]==2 and nums[1]-nums[0]==1: mult,dname=3,"เรียง(×3)"
        return {"score":pts,"is_pok":is_pok,"multiplier":mult,"deng_name":dname}

    # ── ส่งข้อมูล ─────────────────────────────────────────────
    def tx(self, addr, data):
        try: self.sock.sendto(json.dumps(data).encode(), addr)
        except: pass

    def tx_room(self, rid, data):
        for p in self.rooms.get(rid,{}).get("players",{}).values():
            self.tx(p["addr"], data)

    def tx_lobby(self):
        rooms=[{"room_id":rid,"host":r["host_name"],"count":len(r["players"]),
                "min_bet":r["min_bet"],"max_bet":r["max_bet"],"status":r["status"]}
               for rid,r in self.rooms.items()]
        for addr in list(self.lobby):
            self.tx(addr,{"status":"lobby_update","rooms":rooms})

    def tx_players(self, rid):
        r=self.rooms.get(rid)
        if not r: return
        pl=[{"name":p["name"],"balance":p["balance"],"bet":p["bet"],"ready":p["ready"],
             "is_host":(p["name"]==r["host_name"])} for p in r["players"].values()]
        self.tx_room(rid,{"status":"room_update","players":pl,
                          "host_name":r["host_name"],"min_bet":r["min_bet"],"max_bet":r["max_bet"]})

    def all_hands(self, r):
        out={}
        for p in r["players"].values():
            if p["cards"]:
                h=self.score(p["cards"])
                out[p["name"]]={**h,"cards":p["cards"],"balance":p["balance"],"bet":p["bet"]}
        return out

    # ── เทิร์น ────────────────────────────────────────────────
    def next_turn(self, rid):
        r=self.rooms.get(rid)
        if not r or r["status"]!="playing": return
        # กรองคนที่ยังอยู่
        r["turn_order"]=[a for a in r["turn_order"] if a in r["players"]]
        order=r["turn_order"]
        if r["turn_idx"]>=len(order):
            self.end_game(rid); return
        cur=r["players"][order[r["turn_idx"]]]["name"]
        self.tx_room(rid,{"status":"turn_update","current_turn":cur})
        idx=r["turn_idx"]
        t=threading.Timer(15.0,self._timeout,args=[rid,order[idx],idx])
        t.daemon=True; r["turn_timer"]=t; t.start()

    def _timeout(self, rid, astr, idx):
        r=self.rooms.get(rid)
        if r and r.get("turn_idx")==idx and r.get("status")=="playing":
            r["turn_idx"]+=1; self.next_turn(rid)

    def stop_timer(self, r):
        if r.get("turn_timer"): r["turn_timer"].cancel(); r["turn_timer"]=None

    # ── จบเกม ─────────────────────────────────────────────────
    def end_game(self, rid):
        r=self.rooms.get(rid)
        if not r or r["status"]!="playing": return
        self.stop_timer(r); r["status"]="ending"

        hands=self.all_hands(r); hname=r["host_name"]; h=hands.get(hname,{})
        results={}; host_chg=0

        for p in r["players"].values():
            nm=p["name"]
            if nm==hname: continue
            ph=hands.get(nm,{}); bet=p["bet"]
            if   ph.get("is_pok") and h.get("is_pok"): oc="win" if ph["score"]>h["score"] else ("lose" if ph["score"]<h["score"] else "draw")
            elif ph.get("is_pok"):   oc="win"
            elif h.get("is_pok"):    oc="lose"
            elif ph.get("score",0)>h.get("score",0): oc="win"
            elif ph.get("score",0)<h.get("score",0): oc="lose"
            else: oc="draw"
            mult=max(ph.get("multiplier",1),h.get("multiplier",1))
            chg=bet*mult if oc=="win" else (-bet*mult if oc=="lose" else 0)
            p["balance"]=max(0,p["balance"]+chg); host_chg-=chg
            results[nm]={"outcome":oc,"change":chg,"balance":p["balance"],"multiplier":mult,"deng_name":ph.get("deng_name","")}

        for p in r["players"].values():
            if p["name"]==hname:
                p["balance"]=max(0,p["balance"]+host_chg)
                results[hname]={"outcome":"host","change":host_chg,"balance":p["balance"]}

        self.tx_room(rid,{"status":"game_over","all_players_data":hands,"results":results})

        r["status"]="waiting"
        for p in r["players"].values(): p["cards"]=[]; p["bet"]=0; p["ready"]=False

        time.sleep(0.6)

        # เตะคนที่เงินหมด
        for astr,p in list(r["players"].items()):
            if p["balance"]<=0:
                nm=p["name"]
                self.tx(p["addr"],{"status":"kicked","message":"💸 เงินหมด! กลับ Lobby รับเงินใหม่"})
                del r["players"][astr]; self.p2room.pop(astr,None)
                if r["players"]: self.tx_room(rid,{"status":"player_left","message":f"💸 {nm} เงินหมด ออกจากห้อง"})

        if not r["players"]: r["status"]="waiting"; return
        self._check_host(rid); self.tx_players(rid)

    def _abort_game(self, rid, reason):
        """ยกเลิกเกมกลางคัน — คืนเงินเดิมพัน"""
        r=self.rooms.get(rid)
        if not r: return
        self.stop_timer(r)
        for p in r["players"].values(): p["balance"]+=p["bet"]
        r["status"]="waiting"
        for p in r["players"].values(): p["cards"]=[]; p["bet"]=0; p["ready"]=False
        self.tx_room(rid,{"status":"game_aborted","message":reason})
        time.sleep(0.2); self.tx_players(rid)

    def _check_host(self, rid):
        """ถ้าเจ้ามือไม่อยู่แล้ว สุ่มคนใหม่"""
        r=self.rooms.get(rid)
        if not r: return
        names={p["name"] for p in r["players"].values()}
        if r["host_name"] not in names:
            astr=random.choice(list(r["players"]))
            r["host_name"]=r["players"][astr]["name"]; r["host_addr"]=astr
            self.tx(r["players"][astr]["addr"],{"status":"you_are_host","message":"👑 คุณได้เป็นเจ้ามือแล้ว!"})

    # ── ออกห้อง ───────────────────────────────────────────────
    def leave(self, addr, astr, rid, name):
        r=self.rooms.get(rid)
        if not r or astr not in r["players"]: return
        was_host=(name==r["host_name"]); was_playing=(r["status"]=="playing")
        del r["players"][astr]; self.p2room.pop(astr,None)

        if not r["players"]:
            self.stop_timer(r); del self.rooms[rid]; return

        # เจ้ามือออกกลางเกม → ยกเลิกเกม
        if was_playing and was_host:
            self._abort_game(rid,f"⚠️ เจ้ามือ ({name}) ออก — เกมยกเลิก คืนเงินเดิมพันแล้ว")
            self._check_host(rid); self.tx_players(rid); return

        # ผู้เล่นทั่วไปออกกลางเกม → ข้ามเทิร์น
        if was_playing:
            r["turn_order"]=[a for a in r["turn_order"] if a!=astr]
            if r["turn_idx"]>=len(r["turn_order"]):
                self.stop_timer(r)
                self.tx_room(rid,{"status":"player_left","message":f"{name} ออกจากห้อง"})
                time.sleep(0.1); self.end_game(rid); return

        self.tx_room(rid,{"status":"player_left","message":f"{name} ออกจากห้องแล้ว"})
        self._check_host(rid); self.tx_players(rid)

    # ════════════════════════════════════════════════════════
    # Main Loop
    # ════════════════════════════════════════════════════════
    def run(self):
        while True:
            try:
                raw,addr=self.sock.recvfrom(8192)
                msg=json.loads(raw.decode()); act=msg.get("action",""); astr=str(addr)

                if act=="enter_lobby":
                    name=msg.get("name","").strip()
                    taken=set(self.lobby.values())|{p["name"] for r in self.rooms.values() for p in r["players"].values()}
                    if name in taken-{self.lobby.get(addr,"")}:
                        self.tx(addr,{"status":"name_taken","message":f'ชื่อ "{name}" มีคนใช้แล้ว'}); continue
                    self.lobby[addr]=name; self.tx_lobby()

                elif act=="create":
                    mn=max(1,int(msg.get("min_bet",100))); mx=max(mn,int(msg.get("max_bet",1000)))
                    rid=str(random.randint(100000,999999))
                    self.rooms[rid]={
                        "players":{astr:{"name":msg["name"],"cards":[],"balance":START,"bet":0,"ready":False,"addr":addr}},
                        "host_name":msg["name"],"host_addr":astr,
                        "password":msg.get("password","").strip(),
                        "min_bet":mn,"max_bet":mx,"deck":self.new_deck(),
                        "status":"waiting","turn_order":[],"turn_idx":0,"turn_timer":None,
                    }
                    self.p2room[astr]=rid; self.lobby.pop(addr,None)
                    self.tx(addr,{"status":"created","room_id":rid,"is_host":True,
                                  "min_bet":mn,"max_bet":mx,"password":msg.get("password","").strip()})
                    self.tx_lobby()

                elif act=="join":
                    rid=msg.get("room_id","")
                    if rid not in self.rooms: self.tx(addr,{"status":"error","message":"ไม่พบห้องนี้"}); continue
                    r=self.rooms[rid]
                    if r["password"] and r["password"]!=msg.get("password",""):
                        self.tx(addr,{"status":"error","message":"🔒 รหัสผ่านไม่ถูกต้อง"}); continue
                    if len(r["players"])>=6: self.tx(addr,{"status":"error","message":"ห้องเต็ม"}); continue
                    if r["status"] in("playing","ending"): self.tx(addr,{"status":"error","message":"เกมกำลังเล่น รอรอบหน้า"}); continue
                    r["players"][astr]={"name":msg["name"],"cards":[],"balance":START,"bet":0,"ready":False,"addr":addr}
                    self.p2room[astr]=rid; self.lobby.pop(addr,None)
                    self.tx(addr,{"status":"joined","room_id":rid,"is_host":False,
                                  "min_bet":r["min_bet"],"max_bet":r["max_bet"],"password":r["password"]})
                    self.tx_players(rid); self.tx_lobby()

                elif act=="get_room_update":
                    rid=msg.get("room_id","")
                    if rid in self.rooms: self.tx_players(rid)

                elif act=="place_bet":
                    rid=msg.get("room_id",""); r=self.rooms.get(rid)
                    if not r or astr not in r["players"]: continue
                    if r["status"]!="waiting": self.tx(addr,{"status":"error","message":"ไม่อยู่ในช่วงวางเดิมพัน"}); continue
                    p=r["players"][astr]; bet=int(msg.get("bet",r["min_bet"]))
                    if not (r["min_bet"]<=bet<=r["max_bet"]): self.tx(addr,{"status":"error","message":f"เดิมพัน {r['min_bet']}–{r['max_bet']}"}); continue
                    if bet>p["balance"]: self.tx(addr,{"status":"error","message":f"เงินไม่พอ ({p['balance']:,})"}); continue
                    p["bet"]=bet; p["ready"]=True
                    self.tx(addr,{"status":"bet_confirmed","bet":bet}); self.tx_players(rid)

                elif act=="start_game":
                    rid=msg.get("room_id",""); r=self.rooms.get(rid)
                    if not r: continue
                    if r["status"] in("playing","ending"): self.tx(addr,{"status":"error","message":"เกมเริ่มไปแล้ว"}); continue
                    if len(r["players"])<2: self.tx(addr,{"status":"error","message":"ต้องมีอย่างน้อย 2 คน"}); continue
                    not_bet=[p["name"] for p in r["players"].values() if not p["ready"] and p["name"]!=r["host_name"]]
                    if not_bet: self.tx(addr,{"status":"error","message":"ยังไม่วางเดิมพัน:\n"+" ".join(not_bet)}); continue
                    r["status"]="playing"; r["deck"]=self.new_deck()
                    for p in r["players"].values(): p["cards"]=[r["deck"].pop(),r["deck"].pop()]
                    hands=self.all_hands(r)
                    self.tx_room(rid,{"status":"game_started","all_players_data":hands})
                    time.sleep(0.15)
                    poks=[p["name"] for p in r["players"].values() if self.score(p["cards"])["is_pok"]]
                    host_pok=r["host_name"] in poks
                    if poks: self.tx_room(rid,{"status":"pok_alert","pok_players":poks,"host_pok":host_pok}); time.sleep(0.5)
                    if host_pok: self.end_game(rid)
                    else:
                        ha=r["host_addr"]
                        r["turn_order"]=[a for a in r["players"] if a!=ha]+[ha]
                        r["turn_idx"]=0; r["turn_timer"]=None; self.next_turn(rid)

                elif act in("hit","stand"):
                    rid=msg.get("room_id",""); r=self.rooms.get(rid)
                    if not r or r["status"]!="playing": continue
                    self.stop_timer(r)
                    order=r["turn_order"]
                    if r["turn_idx"]>=len(order) or astr!=order[r["turn_idx"]]: continue
                    if act=="hit" and r["deck"]:
                        r["players"][astr]["cards"].append(r["deck"].pop())
                        self.tx_room(rid,{"status":"game_started","all_players_data":self.all_hands(r)}); time.sleep(0.1)
                    r["turn_idx"]+=1; self.next_turn(rid)

                elif act=="leave":
                    rid=msg.get("room_id") or self.p2room.get(astr,""); name=msg.get("name","?")
                    if rid: self.leave(addr,astr,rid,name)
                    self.lobby[addr]=name; self.tx_lobby()

                elif act=="chat":
                    rid=msg.get("room_id","")
                    if rid in self.rooms:
                        self.tx_room(rid,{"status":"chat","sender":msg.get("name","?"),"message":msg.get("message","")})

            except Exception:
                import traceback; traceback.print_exc()


if __name__=="__main__":
    Server().run()