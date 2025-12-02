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
    """查詢單字筆畫與五行"""
    if not word or kanji_db is None: return 0, "?"
    res = kanji_db[kanji_db['character'] == word]
    if not res.empty:
        return int(res.iloc[0]['strokes']), res.iloc[0]['element']
    return 0, "?"

def calculate_five_grids(surname, name):
    """計算三才五格"""
    if not surname or not name: return None
    s1 = get_strokes(surname[0])[0]
    
    if len(name) == 1: # 單名
        n1 = get_strokes(name[0])[0]
        tian = s1 + 1; ren = s1 + n1; di = n1 + 1; wai = 2; total = s1 + n1
        name_tuple = (s1, n1, 0)
    elif len(name) == 2: # 複名
        n1 = get_strokes(name[0])[0]; n2 = get_strokes(name[1])[0]
        tian = s1 + 1; ren = s1 + n1; di = n1 + n2; wai = n2 + 1; total = s1 + n1 + n2
        name_tuple = (s1, n1, n2)
    else: return None 

    return {"天格": tian, "人格": ren, "地格": di, "外格": wai, "總格": total, "姓名筆畫": name_tuple}

def get_81_luck(num):
    """查詢 81 數理吉凶"""
    if score_db is None: return "未知", "資料庫未載入"
    check_num = num % 80 if num > 81 else num 
    if check_num == 0: check_num = 81
    try:
        row = score_db.loc[check_num]
        return row['luck'], row['desc']