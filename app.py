import streamlit as st
import pandas as pd
import os
import datetime
import re
from lunar_python import Lunar, Solar

# ==========================================
# 1. 基礎設定與資料讀取
# ==========================================

st.set_page_config(page_title="紫微姓名工具 ", layout="wide")

@st.cache_data
def load_data():
    try:
        kanji_path = "data/kanji.xlsx"
        score_path = "data/score_81.xlsx"
        sancai_path = "data/sancai.xlsx"
        combo_path = "data/combinations.xlsx"

        kanji_df = pd.read_excel(kanji_path) if os.path.exists(kanji_path) else None
        score_df = pd.read_excel(score_path, index_col="score") if os.path.exists(score_path) else None
        sancai_df = pd.read_excel(sancai_path, index_col="pattern") if os.path.exists(sancai_path) else None
        combo_df = pd.read_excel(combo_path) if os.path.exists(combo_path) else None
        
        return kanji_df, score_df, sancai_df, combo_df
    except Exception as e:
        st.error(f"資料庫讀取失敗: {e}")
        return None, None, None, None

kanji_db, score_db, sancai_db, combo_db = load_data()

# ==========================================
# 2. 核心邏輯：姓名學計算
# ==========================================

def get_strokes(word):
    if not word or kanji_db is None: return 0, "?"
    res = kanji_db[kanji_db['character'] == word]
    if not res.empty:
        return int(res.iloc[0]['strokes']), res.iloc[0]['element']
    return 0, "?"

def calculate_five_grids(surname, name):
    if not surname or not name: return None
    s1 = get_strokes(surname[0])[0]
    
    if len(name) == 1: 
        n1 = get_strokes(name[0])[0]
        tian = s1 + 1; ren = s1 + n1; di = n1 + 1; wai = 2; total = s1 + n1
        name_tuple = (s1, n1, 0)
    elif len(name) == 2:
        n1 = get_strokes(name[0])[0]; n2 = get_strokes(name[1])[0]
        tian = s1 + 1; ren = s1 + n1; di = n1 + n2; wai = n2 + 1; total = s1 + n1 + n2
        name_tuple = (s1, n1, n2)
    else: return None 

    return {"天格": tian, "人格": ren, "地格": di, "外格": wai, "總格": total, "姓名筆畫": name_tuple}

def get_81_luck(num):
    if score_db is None: return "未知", "資料庫未載入"
    check_num = num % 80 if num > 81 else num 
    if check_num == 0: check_num = 81
    try:
        row = score_db.loc[check_num]
        return row['luck'], row['desc'] 
    except: return "未知", ""

def get_sancai_luck(tian, ren, di):
    def num_to_element(n):
        r = n % 10
        if r in [1, 2]: return "木"
        elif r in [3, 4]: return "火"
        elif r in [5, 6]: return "土"
        elif r in [7, 8]: return "金"
        else: return "水"
    pattern = f"{num_to_element(tian)}{num_to_element(ren)}{num_to_element(di)}"
    try:
        if sancai_db is not None:
            row = sancai_db.loc[pattern]
            return pattern, row['luck'], row['desc']
    except: pass
    return pattern, "未知", "無此格局資料"

def get_lucky_strokes_info(joy_element):
    if score_db is None: return []
    target_digits = []
    if joy_element == "木": target_digits = [1, 2]
    elif joy_element == "火": target_digits = [3, 4]
    elif joy_element == "土": target_digits = [5, 6]
    elif joy_element == "金": target_digits = [7, 8]
    elif joy_element == "水": target_digits = [9, 0]
    
    results = []
    for i in range(1, 51):
        if (i % 10) in target_digits:
            luck, desc = get_81_luck(i)
            if "吉" in luck and "凶" not in luck: 
                results.append({"num": i, "luck": luck, "desc": desc})
    return results

# ==========================================
# 3. 核心邏輯：診斷與解析
# ==========================================

def calculate_joy_god(disaster_element, strength="強"):
    if strength == "強":
        rules = {"木": "金", "火": "水", "土": "木", "金": "火", "水": "土"}
        return rules.get(disaster_element, "火")
    else:
        rules = {"木": "水", "火":