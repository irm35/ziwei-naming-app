import streamlit as st
import pandas as pd
import os
import datetime
import re # 引入正規表示式套件來處理文字
from lunar_python import Lunar, Solar

# ==========================================
# 1. 基礎設定與資料讀取
# ==========================================

st.set_page_config(page_title="紫微姓名學架構工具 (全能診斷版)", layout="wide")

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
# 3. 核心邏輯：診斷與解析 (含文字解析器)
# ==========================================

def calculate_joy_god(disaster_element, strength="強"):
    """根據災宮五行計算喜用神 (抑強扶弱邏輯)"""
    if strength == "強":
        rules = {"木": "金", "火": "水", "土": "木", "金": "火", "水": "土"}
        return rules.get(disaster_element, "火")
    else:
        rules = {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}
        return rules.get(disaster_element, "木")

def parse_wenmo_text(text):
    """
    解析文墨天機命盤文字，找出災宮與喜用神
    """
    # 1. 定義地支五行
    zhi_map = {
        "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
        "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"
    }
    
    # 2. 定義煞星關鍵字與權重
    # 化忌權重最重
    ji_keywords = ["生年忌", "化忌", "[忌]"] 
    # 六煞星
    sha_keywords = ["火星", "鈴星", "擎羊", "陀羅", "地空", "地劫", "天空"] # 天空有時視為地空異名
    
    # 3. 切割文字區塊 (找出每個宮位的區段)
    # 文墨天機的宮位標題通常是 "├XX宮[XX]"
    palace_pattern = r"├(.{2,3}宮)\[.(.)\]"  # 抓取 "官祿宮" 和 "戌"
    
    lines = text.split('\n')
    current_palace = None
    current_zhi = None
    palace_scores = {} # { "宮名": {"score": 0, "zhi": "戌", "details": []} }
    
    for line in lines:
        # A. 偵測宮位標題
        match = re.search(palace_pattern, line)
        if match:
            current_palace = match.group(1).strip() # 例如：官祿宮
            current_zhi = match.group(2).strip()    # 例如：戌
            
            # 初始化該宮位分數
            if current_palace not in palace_scores:
                palace_scores[current_palace] = {"score": 0, "zhi": current_zhi, "details": [], "wuxing": zhi_map.get(current_zhi, "土")}
            continue
            
        # B. 偵測星曜與計分 (只在有效宮位區塊內)
        if current_palace:
            # 找化忌
            for kw in ji_keywords:
                if kw in line:
                    palace_scores[current_palace]["score"] += 2
                    palace_scores[current_palace]["details"].append("化忌(+2)")
                    
            # 找六煞
            for kw in sha_keywords:
                if kw in line:
                    # 避免重複計算 (例如有時候文字會有摘要)
                    palace_scores[current_palace]["score"] += 1
                    palace_scores[current_palace]["details"].append(f"{kw}(+1)")

    # 4. 結算最高分
    if not palace_scores:
        return None, None, "無法辨識文字內容，請確認是否為文墨天機格式。"
        
    sorted_palaces = sorted(palace_scores.items(), key=lambda x: x[1]['score'], reverse=True)
    
    top_palace_name = sorted_palaces[0][0]
    top_palace_data = sorted_palaces[0][1]
    
    # 計算喜用神
    joy_god = calculate_joy_god(top_palace_data["wuxing"], "強")
    
    report = f"偵測到煞氣最重：【{top_palace_name}】 ({top_palace_data['score']}分)\n" \
             f"煞星明細：{', '.join(top_palace_data['details'])}\n" \
             f"宮位地支：{top_palace_data['zhi']} (屬{top_palace_data['wuxing']})\n" \
             f"診斷建議：土旺需木剋，建議喜用神為【{joy_god}】" # 範例文字，實際會變動
             
    return top_palace_name, joy_god, report

# ==========================================
# 4. 介面設計 (Streamlit UI)
# ==========================================

st.title("🟣 紫微姓名學架構工具 (全能診斷版)")
st.markdown("---")

# --- 側邊欄 ---
with st.sidebar:
    st.header("1. 輸入命主資料")
    last_name = st.text_input("姓氏", "王")
    first_name = st.text_input("名字", "小明")
    gender = st.radio("性別", ["男", "女"], index=1, horizontal=True)
    
    st.markdown("---")
    st.header("2. 命盤診斷模式")
    
    # 分頁切換
    tab_text, tab_manual = st.tabs(["📋 貼上文字", "🖐️ 手動設定"])
    
    analysis_result = {}
    
    with tab_text:
        st.caption("請將「文墨天機」的命盤文字完整複製貼上：")
        raw_text = st.text_area("命盤文字內容", height=150)
        
        if st.button("解析文字"):
            if len(raw_text) > 50:
                p_name, p_joy, p_report = parse_wenmo_text(raw_text)
                if p_name:
                    st.session_state['ai_zai'] = p_name
                    st.session_state['ai_joy'] = p_joy
                    st.session_state['ai_report'] = p_report
                    st.success("解析成功！")
                else:
                    st.error(p_report)
            else:
                st.warning("文字內容太短，無法解析。")

    # 取得 session state 中的值 (如果有的話)
    default_zai = st.session_state.get('ai_zai', '疾厄宮')
    default_joy = st.session_state.get('ai_joy', '水')
    report_text = st.session_state.get('ai_report', '')
    
    # 手動/自動 同步顯示區
    with tab_manual:
        st.info("若文字解析不準，可在此手動修正。")
        
        # 為了讓 selectbox 能接受 session_state 的預設值，我們需要檢查 index
        palace_opts = ["命宮", "兄弟宮", "夫妻宮", "子女宮", "財帛宮", "疾厄宮", "遷移宮", "交友宮", "官祿宮", "田宅宮", "福德宮", "父母宮"]
        joy_opts = ["木", "火", "土", "金", "水"]
        
        zai_idx = palace_opts.index(default_zai) if default_zai in palace_opts else 5
        joy_idx = joy_opts.index(default_joy) if default_joy in joy_opts else 4
        
        zai_gong_input = st.selectbox("災宮", palace_opts, index=zai_idx)
        joy_element = st.selectbox("喜用神", joy_opts, index=joy_idx)

    st.markdown("---")
    run_analysis = st.button("🚀 開始運算架構", type="primary")

# --- 主畫面 ---
if run_analysis:
    
    st.success(f"🔍 **設定完成**：針對【{zai_gong_input}】進行補救，喜用神鎖定為【{joy_element}】。")
    if report_text:
        st.info(f"📋 **文字診斷報告**：\n{report_text}")
    
    st.markdown("---")
    
    # 1. 現有名字
    st.subheader(f"📊 現有名字分析：{last_name}{first_name}")
    grids = calculate_five_grids(last_name, first_name)
    if grids:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"**天格**: {grids['天格']} ({get_81_luck(grids['天格'])[0]})")
            st.markdown(f"**人格**: {grids['人格']} ({get_81_luck(grids['人格'])[0]})  👈 核心")
            st.markdown(f"**地格**: {grids['地格']} ({get_81_luck(grids['地格'])[0]})")
            st.markdown(f"**外格**: {grids['外格']} ({get_81_luck(grids['外格'])[0]})")
            st.markdown(f"**總格**: {grids['總格']} ({get_81_luck(grids['總格'])[0]})")
            
            ren_elem = ["水","木","木","火","火","土","土","金","金","水"][grids['人格']%10]
            if ren_elem == joy_element:
                st.success(f"✅ 人格五行 ({ren_elem}) 符合喜用神！")
            else:
                st.warning(f"⚠️ 人格五行 ({ren_elem}) 未補強喜用神 ({joy_element})。")
        with col2:
            pattern, luck, desc = get_sancai_luck(grids['天格'], grids['人格'], grids['地格'])
            st.metric("三才配置", pattern, luck)
            st.info(f"**【架構優點】**：{desc}") 

    st.markdown("---")

    # 2. 正式命名推薦 (筆畫架構 + 優點)
    st.subheader(f"📐 正式命名架構推薦 (針對姓氏：{last_name}，喜用：{joy_element})")
    st.info("以下提供符合「三才五格」與「喜用神」的最佳筆畫組合，請依據筆畫數自行挑選漢字。")
    
    if combo_db is not None:
        s_stroke = get_strokes(last_name)[0]
        valid_combos = combo_db[combo_db['surname_strokes'] == s_stroke]
        
        if not valid_combos.empty:
            recommendations = valid_combos.head(5) 
            
            for idx, row in recommendations.iterrows():
                n1_s = row['n1_strokes']
                n2_s = row['n2_strokes']
                total_s = s_stroke + n1_s + n2_s
                
                tian = s_stroke + 1
                ren = s_stroke + n1_s
                di = n1_s + n2_s
                pat, sancai_luck, sancai_desc = get_sancai_luck(tian, ren, di)
                total_luck, total_desc = get_81_luck(total_s)
                
                with st.expander(f"✨ 方案 {idx+1}：總格 {total_s} 畫 ({total_luck})"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("姓氏", f"{s_stroke} 畫", last_name)
                    c2.metric("名字首字", f"{n1_s} 畫", f"建議五行：{joy_element}")
                    c3.metric("名字次字", f"{n2_s} 畫", "五行不限")
                    
                    st.markdown("#### 🎯 核心優點解析")
                    st.markdown(f"- **總格運勢 ({total_luck})**：{total_desc}")
                    st.markdown(f"- **三才配置 ({sancai_luck})**：{sancai_desc}")
                    
        else:
            st.warning("資料庫中暫無適合此姓氏筆畫的完美組合。")
    else:
        st.error("找不到 combinations.xlsx。")
            
    st.markdown("---")
    
    # 3. 小名/乳名推薦 (筆畫 + 意義)
    st.subheader(f"👶 旺運小名/乳名 (吉數與含義)")
    st.info(f"以下為五行屬「{joy_element}」且數理為「吉」的筆畫數，適合用於小名補運：")
    
    lucky_info_list = get_lucky_strokes_info(joy_element)
    
    if lucky_info_list:
        for info in lucky_info_list:
            num = info['num']
            luck = info['luck']
            desc = info['desc']
            with st.container():
                c1, c2 = st.columns([1, 4])
                with c1:
                    st.button(f"{num} 畫", key=f"ln_{num}", help=f"五行屬{joy_element}")
                with c2:
                    st.markdown(f"**【{luck}】** {desc}")
                st.divider() 
    else:
        st.write("查無對應筆畫。")