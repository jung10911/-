import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 페이지 설정
st.set_page_config(page_title="국내 증시 액면가 이하 종목 추출기", layout="wide")

def get_filtered_market_data(market_code):
    """
    market_code: KOSPI=0, KOSDAQ=1
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
    }
    
    # 1. 마지막 페이지 번호 찾기
    base_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={market_code}"
    res = requests.get(base_url, headers=headers)
    soup = BeautifulSoup(res.text, 'lxml')
    
    last_page_tag = soup.find('td', class_='pgRR')
    last_page = int(last_page_tag.a['href'].split('page=')[-1]) if last_page_tag else 1

    all_dfs = []
    
    # 스트림릿 상태 표시
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 2. 페이지별 크롤링 진행 (액면가 필드 포함)
    for page in range(1, last_page + 1):
        url = f"{base_url}&fieldIds=face_value&page={page}"
        res = requests.get(url, headers=headers)
        
        df_list = pd.read_html(res.text, encoding='euc-kr')
        df = df_list[1]
        
        # 불필요한 행 및 열 제거
        df = df.dropna(subset=['종목명'])
        df = df.loc[:, ~df.columns.str.contains('Unnamed')]
        
        all_dfs.append(df)
        
        # 프로그레스 바 업데이트
        progress_bar.progress(page / last_page)
        status_text.text(f"데이터 수집 및 분석 중... ({page}/{last_page} 페이지)")
        
    final_df = pd.concat(all_dfs, ignore_index=True)
    
    # 순위 컬럼(N) 제거
    if 'N' in final_df.columns:
        final_df = final_df.drop(columns=['N'])
        
    # 3. 데이터 전처리 (결측치 및 하이픈을 0으로 변환)
    final_df = final_df.replace('-', '0').fillna('0')
    
    # 4. 필터링을 위한 숫자형 데이터 변환 (콤마 제거)
    # 비교 연산을 위해 임시로 숫자형(numeric) 변수를 만듭니다.
    current_price = pd.to_numeric(final_df['현재가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    face_value = pd.to_numeric(final_df['액면가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # 5. 핵심 조건 필터링: 현재주가가 액면가보다 낮은 기업
    # (액면가나 현재가가 0인 예외 상황은 제외)
    condition = (face_value > 0) & (current_price > 0) & (current_price < face_value)
    
    # 조건에 맞는 데이터만 추출 후 인덱스 리셋
    filtered_df = final_df[condition].reset_index(drop=True)
    
    # 진행 완료 메시지 초기화
    status_text.empty()
    progress_bar.empty()
    
    return filtered_df

# UI 구성
st.title("📉 주가 < 액면가 종목 추출기")
st.markdown("**현재주가**가 **액면가**보다 낮게 거래되고 있는 KOSPI 및 KOSDAQ 종목을 찾아냅니다.")

market_choice = st.sidebar.selectbox("시장 선택", ["KOSPI", "KOSDAQ"])
market_map = {"KOSPI": "0", "KOSDAQ": "1"}

if st.sidebar.button("조건 검색 실행"):
    try:
        with st.spinner(f"{market_choice} 데이터를 수집하고 조건을 필터링하고 있습니다..."):
            df_result = get_filtered_market_data(market_map[market_choice])
            
            st.subheader(f"✅ {market_choice} 검색 결과")
            if len(df_result) > 0:
                st.write(f"현재주가가 액면가보다 낮은 종목이 총 **{len(df_result)}개** 확인되었습니다.")
                st.dataframe(df_result, use_container_width=True)
                
                # CSV 다운로드
                csv = df_result.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    label="📥 필터링 결과 CSV 다운로드",
                    data=csv,
                    file_name=f"undervalued_face_value_{market_choice}.csv",
                    mime='text/csv',
                )
            else:
                st.info(f"현재 {market_choice} 시장에는 현재주가가 액면가보다 낮은 종목이 없습니다.")
                
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
else:
    st.info("왼쪽 사이드바에서 시장을 선택한 후 '조건 검색 실행' 버튼을 눌러주세요.")
