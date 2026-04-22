import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import io
from urllib.parse import unquote

# 1. 페이지 설정
st.set_page_config(page_title="G2B 마케팅 공고 분석기", layout="wide")

# 2. 보안 설정: Secrets에서 API_KEY 로드
try:
    # Streamlit 관리 페이지의 [Settings] > [Secrets]에서 API_KEY = "내키" 설정 필수
    MY_API_KEY = st.secrets["API_KEY"]
except Exception:
    st.error("🔑 Streamlit Secrets에서 'API_KEY'를 먼저 설정해주세요.")
    st.stop()

st.title("🏛️ 나라장터 마케팅/뉴미디어 공고 실시간 큐레이션")

# 3. 요청하신 핵심 키워드 리스트
TARGET_KEYWORDS = [
    "뉴미디어", "유튜브", "sns", "온라인홍보", "농촌", 
    "문화", "관광", "서포터즈", "외국인", "글로벌", "홍보", "캠페인",
    "영상", "마케팅", "브랜딩", "통합 홍보"
]

@st.cache_data(ttl=600)
def fetch_g2b_data():
    # 용역 입찰공고 조회를 위한 엔드포인트
    endpoint = "http://apis.data.go.kr/1230000/BidPublicInfoService05/getBidPblancListInfoServcPPSSrch"
    
    # 인증키 인코딩 문제 방지를 위한 디코딩 처리
    decoded_key = unquote(MY_API_KEY)
    
    # 기간 설정: 오늘 기준 최근 15일
    now = datetime.now()
    start_dt = (now - timedelta(days=15)).strftime('%Y%m%d0000')
    end_dt = now.strftime('%Y%m%d2359')

    # 필수 파라미터 (inqryDiv: 1 필수 반영으로 500 에러 방지)
    params = {
        'serviceKey': decoded_key,
        'numOfRows': '999',
        'pageNo': '1',
        'inqryDiv': '1',  # 공고게시일 기준
        'type': 'json',
        'bidNtceDtFrom': start_dt,
        'bidNtceDtTo': end_dt
    }

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(endpoint, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # 인증키 오류 시 XML로 에러가 오는 경우 처리
            if response.text.startswith("<?xml"):
                return None, f"인증키 오류: {response.text[:100]}"
            
            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', [])
            
            if not items:
                return pd.DataFrame(), None
            
            return pd.DataFrame(items), None
        else:
            return None, f"서버 응답 오류 (HTTP {response.status_code})"
            
    except Exception as e:
        return None, f"연결 오류: {str(e)}"

# --- UI 실행 ---
st.info(f"📋 **모니터링 조건:** 1억 이상 / 최근 15일 / {len(TARGET_KEYWORDS)}개 핵심 키워드")

if st.button("🚀 실시간 공고 분석 시작"):
    with st.spinner("조달청 서버에서 데이터를 분석 중입니다..."):
        df_raw, err = fetch_g2b_data()

    if err:
        st.error(f"❌ {err}")
    elif df_raw is not None:
        if not df_raw.empty:
            # 1. 예산 필터링: 1억(100,000,000) 이상
            df_raw['bdgtAmt'] = pd.to_numeric(df_raw['bdgtAmt'], errors='coerce').fillna(0)
            df_rich = df_raw[df_raw['bdgtAmt'] >= 100000000].copy()

            # 2. 키워드 필터링 (공고명 기준)
            pattern = '|'.join(TARGET_KEYWORDS)
            df_filtered = df_rich[df_rich['bidNtceNm'].str.contains(pattern, case=False, na=False)].copy()

            if not df_filtered.empty:
                # 출력 컬럼 정리
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
                
                # 데이터 출력
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
                    final_df.to_excel(writer, index=False, sheet_name='입찰공고')
                st.download_button(
                    label="📥 분석 결과 엑셀 저장",
                    data=output.getvalue(),
                    file_name=f"G2B_Analysis_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
            else:
                st.warning("조건(1억 이상+키워드)에 맞는 공고가 현재 없습니다.")
        else:
            st.info("최근 15일 이내 등록된 공고 자체가 없습니다.")
