import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import pickle

db_path = "/home/hgeon/gravity/LangAIAgent/backend/data/checkpoints.sqlite"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT checkpoint_id, checkpoint FROM checkpoints WHERE thread_id = '9e0ioe' ORDER BY datetime(checkpoint_id) ASC")
rows = cur.fetchall()

print(f"Total checkpoints found: {len(rows)}")

for idx, (cid, blob) in enumerate(rows):
    try:
        cp = pickle.loads(blob)
        state = cp.get("channel_values", {})
        
        sub_index = state.get("current_sub_step_index")
        chap_idx = state.get("current_chapter_index")
        chap_plan = state.get("chapter_plan")
        iter_count = state.get("iteration_count")
        step_idx = state.get("current_step_index")
        
        if step_idx == 0 and sub_index == 1:
            chap_len = len(chap_plan) if chap_plan else 0
            print(f"[{idx}] {cid} | ch_idx: {chap_idx} | len(chap_plan): {chap_len} | iter: {iter_count}")
    except Exception as e:
        print(f"Error unpickling: {e}")
        break
conn.close()
