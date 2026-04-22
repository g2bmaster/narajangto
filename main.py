import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import io
from urllib.parse import unquote

# 1. 페이지 설정
st.set_page_config(page_title="G2B 마케팅 공고 분석기", layout="wide")

# 2. 보안 설정: Streamlit Secrets 확인
try:
    # 숫자로 된 일반 인증키(Decoding) 사용을 권장합니다.
    MY_API_KEY = st.secrets["API_KEY"]
except Exception:
    st.error("🔑 Streamlit 관리 페이지의 [Settings] > [Secrets]에서 API_KEY를 설정해주세요.")
    st.stop()

st.title("🏛️ 나라장터 실시간 마케팅 큐레이션")

# 3. 요청하신 핵심 키워드 리스트 (확장 버전)
TARGET_KEYWORDS = [
    "뉴미디어", "유튜브", "sns", "온라인홍보", "농촌", 
    "문화", "관광", "서포터즈", "외국인", "글로벌", "홍보", "캠페인",
    "영상", "마케팅", "브랜딩"
]

@st.cache_data(ttl=600)
def fetch_g2b_data():
    # 500 에러 방지를 위한 필수 파라미터가 포함된 엔드포인트 (용역 입찰공고)
    endpoint = "http://apis.data.go.kr/1230000/BidPublicInfoService05/getBidPblancListInfoServcPPSSrch"
    
    # 인증키 디코딩 처리 (중복 인코딩 방지)
    decoded_key = unquote(MY_API_KEY)
    
    # 기간 설정: 오늘 기준 최근 15일
    now = datetime.now()
    start_dt = (now - timedelta(days=15)).strftime('%Y%m%d0000')
    end_dt = now.strftime('%Y%m%d2359')

    # 필수 파라미터 (inqryDiv: 1 필수)
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
        # headers를 추가하여 일반 브라우저 요청처럼 위장 (차단 방지)
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(endpoint, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # XML 에러 메시지가 섞여 오는지 체크
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

# --- UI 및 필터링 로직 ---
st.info(f"📋 **모니터링 조건:** 1억 이상 / 최근 15일 / {len(TARGET_KEYWORDS)}개 키워드")

if st.button("🚀 실시간 공고 분석 시작"):
    with st.spinner("조달청 서버에서 데이터를 긁어오는 중..."):
        df_raw, err = fetch_g2b_data()

    if err:
        st.error(f"❌ {err}")
        st.warning("팁: 인증키가 Encoding 버전이라면 Decoding 버전으로 바꿔보세요.")
    elif df_raw is not None:
        if not df_raw.empty:
            # 1. 예산(배정예산) 필터링: 1억 이상
            df_raw['bdgtAmt'] = pd.to_numeric(df_raw['bdgtAmt'], errors='coerce').fillna(0)
            df_rich = df_raw[df_raw['bdgtAmt'] >= 100000000].copy()

            # 2. 키워드 필터링 (공고명 기준)
            pattern = '|'.join(TARGET_KEYWORDS)
            df_filtered = df_rich[df_rich['bidNtceNm'].str.contains(pattern, case=False, na=False)].copy()

            if not df_filtered.empty:
                # 출력용 컬럼 정리
                display_cols = {
                    'bidNtceNm': '공고명',
                    'bdgtAmt': '배정예산',
                    'ntceInsttNm': '발주기관',
                    'bidNtceDt': '게시일시',
                    'bidClseDt': '마감일시',
                    'bidNtceUrl': '상세링크'
                }
                final_df = df_filtered[list(display_cols.keys())].rename(columns=display_cols)
                final_df = final_df.sort_values('게시일시', ascending=False)

                st.success(f"🎯 최적화된 공고 {len(final_df)}건을 찾았습니다!")
                
                # 데이터 프레임 출력
                st.dataframe(
                    final_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "배정예산": st.column_config.NumberColumn(format="₩%d"),
                        "상세링크": st.column_config.LinkColumn("링크 🔗")
                    }
                )

                # 엑셀 다운로드 기능
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df.to_excel(writer, index=False, sheet_name='입찰리스트')
                st.download_button(
                    label="📥 분석 결과 엑셀로 저장",
                    data=output.getvalue(),
                    file_name=f"G2B_Analysis_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
            else:
                st.warning("1억 이상 공고 중 해당 키워드를 포함한 건이 없습니다.")
        else:
            st.info("최근 15일 이내에 등록된 용역 공고가 없습니다.")
