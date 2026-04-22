import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import io

# 1. 페이지 레이아웃 및 제목
st.set_page_config(page_title="G2B 마케팅 큐레이터", layout="wide")
st.title("🏛️ 나라장터 실시간 마케팅 공고 분석")

# 2. 보안 설정 (Secrets)
try:
    MY_API_KEY = st.secrets["API_KEY"]
except Exception:
    st.error("🔑 Streamlit Secrets에 'API_KEY'를 설정해주세요.")
    st.stop()

# 3. 요청하신 모든 키워드 리스트
TARGET_KEYWORDS = [
    "뉴미디어", "유튜브", "sns", "온라인홍보", "농촌", "문화", 
    "관광", "서포터즈", "외국인", "글로벌", "홍보", "캠페인",
    "영상", "마케팅", "브랜딩", "통합 홍보"
]

@st.cache_data(ttl=600)
def fetch_g2b_data():
    # 이미지 12번 항목: 용역 입찰공고 검색 엔드포인트
    endpoint = "http://apis.data.go.kr/1230000/BidPublicInfoService05/getBidPblancListInfoServcPPSSrch"
    
    # 기간 설정 (최근 15일)
    now = datetime.now()
    start_dt = (now - timedelta(days=15)).strftime('%Y%m%d0000')
    end_dt = now.strftime('%Y%m%d2359')

    # 핵심 수정: 인증키를 params에 넣지 않고 URL에 직접 붙여서 인코딩 문제를 원천 차단
    full_url = (
        f"{endpoint}?serviceKey={MY_API_KEY}"
        f"&numOfRows=999&pageNo=1&type=json"
        f"&inqryDiv=1" # 공고게시일 기준
        f"&bidNtceDtFrom={start_dt}&bidNtceDtTo={end_dt}"
    )

    try:
        # User-Agent를 추가하여 차단 방지
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(full_url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            # XML 에러 응답 확인 (인증키 문제 시 XML로 옴)
            if response.text.startswith("<?xml"):
                return None, f"인증키 권한 오류: {response.text[:100]}"
            
            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', [])
            
            # 데이터가 없을 경우(03) 처리
            if not items:
                return pd.DataFrame(), None
            
            return pd.DataFrame(items), None
        else:
            return None, f"서버 오류 (HTTP {response.status_code})"
    except Exception as e:
        return None, f"시스템 오류: {str(e)}"

# --- 실행 UI ---
st.info(f"📋 **모니터링:** 1억 이상 / 15일 이내 / {len(TARGET_KEYWORDS)}개 키워드")

if st.button("🚀 실시간 공고 분석 시작"):
    with st.spinner("이미지 규격에 맞춰 조달청 데이터를 분석 중입니다..."):
        df_raw, err = fetch_g2b_data()

    if err:
        st.error(f"❌ {err}")
        st.info("💡 팁: 'Encoding' 키 대신 'Decoding' 키를 Secrets에 넣어보세요.")
    elif df_raw is not None:
        if not df_raw.empty:
            # 1. 예산 필터링 (1억 이상)
            df_raw['bdgtAmt'] = pd.to_numeric(df_raw['bdgtAmt'], errors='coerce').fillna(0)
            df_rich = df_raw[df_raw['bdgtAmt'] >= 100000000].copy()

            # 2. 키워드 필터링
            pattern = '|'.join(TARGET_KEYWORDS)
            df_filtered = df_rich[df_rich['bidNtceNm'].str.contains(pattern, case=False, na=False)].copy()

            if not df_filtered.empty:
                # 컬럼명 매핑 및 정리
                cols = {
                    'bidNtceNm': '공고명',
                    'bdgtAmt': '배정예산',
                    'ntceInsttNm': '발주기관',
                    'bidNtceDt': '게시일시',
                    'bidClseDt': '마감일시',
                    'bidNtceUrl': '상세링크'
                }
                final_df = df_filtered[list(cols.keys())].rename(columns=cols)
                final_df = final_df.sort_values('게시일시', ascending=False)

                st.success(f"🎯 맞춤 공고 {len(final_df)}건 발견")
                st.dataframe(
                    final_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "배정예산": st.column_config.NumberColumn(format="₩%d"),
                        "상세링크": st.column_config.LinkColumn("이동 🔗")
                    }
                )

                # 엑셀 다운로드
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df.to_excel(writer, index=False, sheet_name='G2B_List')
                st.download_button(
                    label="📥 분석 결과 엑셀 저장",
                    data=output.getvalue(),
                    file_name=f"G2B_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
            else:
                st.warning("1억 이상 공고 중 해당 키워드를 포함한 건이 없습니다.")
        else:
            st.info("최근 15일 이내 등록된 입찰 데이터가 없습니다.")
