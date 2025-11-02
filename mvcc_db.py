versions = {}
transactions = {}
tx_counter = 0
current_tx = None
def init_db():
    global versions, transactions, tx_counter, current_tx
    versions, transactions, tx_counter, current_tx = {}, {}, 0, None; load()
def tx_start():
    global tx_counter, current_tx
    tx_counter += 1; tx_id = f"tx{tx_counter}"; transactions[tx_id] = {"timestamp": tx_counter, "snapshot_ts": tx_counter, "state": "active", "writes": [], "reads": []}; current_tx = tx_id; return tx_id
def tx_commit(tx_id):
    if tx_id not in transactions or transactions[tx_id]["state"] != "active": return False
    tx = transactions[tx_id]
    for r_id in tx.get("reads", []):
        if r_id in versions and versions[r_id] and versions[r_id][0]["timestamp"] > tx["timestamp"]: return False
    tx["state"] = "committed"; return True
def tx_abort(tx_id):
    global current_tx
    if tx_id not in transactions: return False
    for r_id, _ in transactions[tx_id]["writes"]:
        if r_id in versions and versions[r_id]: versions[r_id].pop(0)
    transactions.pop(tx_id); current_tx = None if current_tx == tx_id else current_tx
    return True
def read_version(record_id, snapshot_ts):
    if record_id not in versions: return None
    for v in versions[record_id]:
        if v["timestamp"] <= snapshot_ts: return None if v.get("deleted", False) else v["data"]
    return None
def tx_read(record_id):
    if not (current_tx and current_tx in transactions): return None
    transactions[current_tx].setdefault("reads", []).append(record_id)
    return read_version(record_id, transactions[current_tx]["snapshot_ts"])
def tx_write(record_id, data):
    if not current_tx: return False
    tx = transactions[current_tx]
    if record_id in versions and versions[record_id]:
        lv = versions[record_id][0]
        if lv["timestamp"] > tx["timestamp"] and lv["tx_id"] != current_tx: tx_abort(current_tx); return False
    if record_id not in versions: versions[record_id] = []
    versions[record_id].insert(0, {"timestamp": tx_counter, "tx_id": current_tx, "data": data, "deleted": False})
    transactions[current_tx]["writes"].append((record_id, 0)); return True
def tx_delete(record_id):
    if not current_tx: return False
    v = read_version(record_id, transactions[current_tx]["snapshot_ts"])
    if v is None: return False
    if record_id not in versions: versions[record_id] = []
    versions[record_id].insert(0, {"timestamp": tx_counter, "tx_id": current_tx, "data": v, "deleted": True})
    transactions[current_tx]["writes"].append((record_id, 0)); return True
def create(r_id, d): tx_start(); r = tx_write(r_id, d); (tx_commit if r else tx_abort)(current_tx) if current_tx else None; return r
def read(r_id): tx_start(); r = tx_read(r_id); tx_commit(current_tx); return r
def update(r_id, d): tx_start(); r = tx_write(r_id, d); (tx_commit if r else tx_abort)(current_tx) if current_tx else None; return r
def delete(r_id): tx_start(); r = tx_delete(r_id); (tx_commit if r else tx_abort)(current_tx) if current_tx else None; return r
def gc():
    active = [t["snapshot_ts"] for t in transactions.values() if t["state"] == "active"]
    if not active: return
    oldest_ts = min(active)
    for r_id in versions:
        while len(versions[r_id]) > 1 and versions[r_id][-1]["timestamp"] < oldest_ts: versions[r_id].pop()
def save():
    global versions, transactions, tx_counter
    try: open("mvcc_db.dat", "w").write(repr(versions) + "\n" + repr(transactions) + "\n" + str(tx_counter))
    except: pass
def load():
    global versions, transactions, tx_counter
    try: f = open("mvcc_db.dat", "r"); versions, transactions, tx_counter = eval(f.readline()), eval(f.readline()), int(f.readline()); f.close(); return True
    except: return False
def show_version_chain(record_id):
    if record_id not in versions: print("Record not found"); return
    for i, v in enumerate(versions[record_id]): print(f"v{i}: ts={v['timestamp']}, tx={v['tx_id']}, deleted={v.get('deleted', False)}, data={v['data']}")
def read_at(r_id, ts): return read_version(r_id, int(ts))
def backup(backup_ts=0):
    incr = {r_id: vs for r_id, vs in {r_id: [v for v in vs if v["timestamp"] > backup_ts] for r_id, vs in versions.items()}.items() if vs}
    try: open(f"backup_{tx_counter}.dat", "w").write(repr(incr) + "\n" + str(backup_ts) + "\n" + str(tx_counter)); return True
    except: return False
def restore(bf):
    global versions, tx_counter
    try: f = open(bf, "r"); iv, bt, bc = eval(f.readline()), int(f.readline()), int(f.readline()); f.close(); [versions.setdefault(r_id, []).extend(vs) or versions[r_id].sort(key=lambda v: -v["timestamp"]) for r_id, vs in iv.items()]; tx_counter = max(tx_counter, bc); return True
    except: return False
def main():
    init_db(); print("MVCC Database - Commands: create, read, update, delete, versions, txs, tx_start, tx_read, tx_commit, gc, backup, restore, read_at, quit")
    while True:
        cmd = input("> ").split(maxsplit=2)
        if not cmd: continue
        if cmd[0] == "quit": save(); break
        elif cmd[0] == "create" and len(cmd) == 3: print("OK" if create(cmd[1], cmd[2]) else "FAIL")
        elif cmd[0] == "read" and len(cmd) == 2: r = read(cmd[1]); print(r if r else "Not found")
        elif cmd[0] == "update" and len(cmd) == 3: print("OK" if update(cmd[1], cmd[2]) else "FAIL")
        elif cmd[0] == "delete" and len(cmd) == 2: print("OK" if delete(cmd[1]) else "FAIL")
        elif cmd[0] == "versions" and len(cmd) == 2: show_version_chain(cmd[1])
        elif cmd[0] == "txs": [print(f"{tx_id}: ts={tx['timestamp']}, state={tx['state']}") for tx_id, tx in transactions.items()]
        elif cmd[0] == "tx_start": print(f"{tx_start()} started")
        elif cmd[0] == "tx_read" and len(cmd) == 2: r = tx_read(cmd[1]); print(r if r else "Not found")
        elif cmd[0] == "tx_commit" and len(cmd) == 2: print("OK" if tx_commit(cmd[1]) else "FAIL")
        elif cmd[0] == "gc": gc()
        elif cmd[0] == "backup": print("OK" if backup(int(cmd[1]) if len(cmd) > 1 else 0) else "FAIL")
        elif cmd[0] == "restore" and len(cmd) == 2: print("OK" if restore(cmd[1]) else "FAIL")
        elif cmd[0] == "read_at" and len(cmd) == 3: r = read_at(cmd[1], cmd[2]); print(r if r else "Not found")
        else: print("Invalid command")
if __name__ == "__main__": main()
