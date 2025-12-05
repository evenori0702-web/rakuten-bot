import streamlit as st
import requests
import json
import datetime

# ==========================================
#  設定エリア
# ==========================================
# secrets（金庫）からキーを読み込む設定
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
RAKUTEN_APP_ID = st.secrets["RAKUTEN_APP_ID"]
RAKUTEN_AFF_ID = st.secrets["RAKUTEN_AFF_ID"]

# ==========================================
#  ページ設定 & デザイン変更
# ==========================================
st.set_page_config(page_title="楽天市場検索Bot", page_icon="🛍️")

# CSSで微調整（色はconfig.tomlで管理しているので、ここはサイズや非表示設定のみ）
st.markdown("""
    <style>
    /* 1. スマホでタイトルが改行しないように文字サイズを調整 */
    @media (max-width: 640px) {
        h1 {
            font-size: 1.8rem !important; /* 文字を少し小さく */
        }
    }
    
    /* 2. 余計なリンクやアイコンを隠す */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 右上のメニューボタンなどを消す */
    [data-testid="stToolbar"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🛍️ 楽天市場検索Bot")

# ==========================================
#  関数定義エリア
# ==========================================

# 1. Gemini APIを呼び出す関数
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"エラー: {e}"

# 2. 楽天市場APIを呼び出す関数
def search_rakuten_items(keyword):
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {
        "format": "json",
        "keyword": keyword,
        "applicationId": RAKUTEN_APP_ID,
        "affiliateId": RAKUTEN_AFF_ID,
        "hits": 3,           # ★コメント生成に時間がかかるため、3件に絞りました
        "sort": "standard"
    }
    
    try:
        res = requests.get(url, params=params)
        data = res.json()
        if "Items" in data:
            return [item['Item'] for item in data['Items']]
        return []
    except:
        return []

# ==========================================
#  メイン処理
# ==========================================

# セッション状態の初期化
if "messages" not in st.session_state:
    st.session_state.messages = []
if "previous_topic" not in st.session_state:
    st.session_state.previous_topic = "なし"

# チャット履歴の表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "items" in message:
            for item_data in message["items"]:
                # 保存された商品情報を表示
                with st.container():
                    cols = st.columns([1, 2])
                    with cols[0]:
                        st.image(item_data['image'], use_container_width=True)
                    with cols[1]:
                        st.markdown(f"**{item_data['name']}**")
                        st.markdown(f":red[**¥{item_data['price']:,}**]")
                        # 保存しておいたAIコメントを表示
                        st.info(f"💡 {item_data['ai_comment']}")
                        st.link_button("👉 楽天で見る", item_data['url'])
                st.divider()

# ユーザー入力
if user_input := st.chat_input("何をお探しですか？"):
    
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("商品検索中…少々お待ちください"):
            
            # --- ロジック ---
            previous_topic = st.session_state.previous_topic
            
            # キーワード決定プロンプト
            system_prompt = f"""
            ユーザー入力: "{user_input}"
            直前の文脈: "{previous_topic}"
            
            楽天市場で商品を検索するための最適なキーワードを1つだけ教えて。
            雑談なら回答のみ、検索が必要なら【SEARCH:キーワード】の形式で出力して。
            """

            gemini_response = call_gemini(system_prompt)
            final_reply_text = gemini_response
            found_items_data = [] # 履歴保存用のリスト

            if "【SEARCH:" in gemini_response:
                keyword = gemini_response.replace("【SEARCH:", "").replace("】", "").strip()
                st.session_state.previous_topic = keyword
                
                # 楽天検索実行
                items = search_rakuten_items(keyword)
                
                if items:
                    final_reply_text = f"「{keyword}」のおすすめ商品を3つ厳選しました！"
                    st.markdown(final_reply_text) # 先にメッセージを表示

                    # ★ここが変更点：ループしながら1つずつAIコメントを生成
                    for item in items:
                        with st.container():
                            cols = st.columns([1, 2])
                            
                            # 画像URL取得
                            img_url = item['mediumImageUrls'][0]['imageUrl'] if item['mediumImageUrls'] else ""
                            
                            with cols[0]:
                                st.image(img_url, use_container_width=True)
                            
                            with cols[1]:
                                st.markdown(f"**{item['itemName'][:30]}...**")
                                st.markdown(f":red[**¥{int(item['itemPrice']):,}**]")
                                
                                # ★AIにおすすめコメントを書かせる
                                comment_prompt = f"""
                                商品名: {item['itemName']}
                                価格: {item['itemPrice']}円
                                キャッチコピー: {item['itemCaption'][:100]}
                                
                                この商品の魅力を伝える、100文字以内の「おすすめコメント」を書いて。
                                """
                                ai_comment = call_gemini(comment_prompt)
                                st.info(f"💡 {ai_comment}")
                                
                                st.link_button("👉 楽天で見る", item['affiliateUrl'])
                            
                            st.divider()
                            
                            # 履歴保存用のデータを作成
                            found_items_data.append({
                                "name": item['itemName'][:30] + "...",
                                "price": int(item['itemPrice']),
                                "image": img_url,
                                "url": item['affiliateUrl'],
                                "ai_comment": ai_comment
                            })

                else:
                    final_reply_text = f"「{keyword}」は見つかりませんでした💦"
                    st.markdown(final_reply_text)
            else:
                st.markdown(final_reply_text)

    # 履歴に保存
    message_data = {"role": "assistant", "content": final_reply_text}
    if found_items_data:
        message_data["items"] = found_items_data
    

    st.session_state.messages.append(message_data)




