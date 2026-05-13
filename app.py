import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

# 페이지 설정
st.set_page_config(page_title="국내 증시 액면가 추출기", layout="wide")

def get_market_data(market_code):
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
    if last_page_tag:
        last_page = int(last_page_tag.a['href'].split('page=')[-1])
    else:
        last_page = 1

    all_dfs = []
    
    # 스트림릿 프로그레스 바
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 2. 페이지별 크롤링 (액면가 필드 포함)
    for page in range(1, last_page + 1):
        # fieldIds=face_value 파라미터를 추가하여 액면가 데이터를 강제로 포함
        url = f"{base_url}&fieldIds=face_value&page={page}"
        res = requests.get(url, headers=headers)
        
        # pandas read_html로 테이블 추출
        df_list = pd.read_html(res.text, encoding='euc-kr')
        df = df_list[1] # 주식 목록은 보통 두 번째 테이블
        
        # 불필요한 행(구분선 등) 및 열 제거
        df = df.dropna(subset=['종목명'])
        df = df.loc[:, ~df.columns.str.contains('Unnamed')]
        
        all_dfs.append(df)
        
        # 상태 업데이트
        progress = page / last_page
        progress_bar.progress(progress)
        status_text.text(f"데이터 수집 중... ({page}/{last_page} 페이지)")
        
    final_df = pd.concat(all_dfs, ignore_index=True)
    # 순위 컬럼 제거 및 인덱스 재설정
    if 'N' in final_df.columns:
        final_df = final_df.drop(columns=['N'])
    
    return final_df

# UI 구성
st.title("📊 국내 상장사 액면가 데이터 추출")
st.markdown("네이버 페이 증권의 데이터를 활용하여 KOSPI/KOSDAQ 종목의 **액면가**를 수집합니다.")

market_choice = st.sidebar.selectbox("시장 선택", ["KOSPI", "KOSDAQ"])
market_map = {"KOSPI": "0", "KOSDAQ": "1"}

if st.sidebar.button("데이터 불러오기"):
    try:
        with st.spinner(f"{market_choice} 데이터를 분석 중입니다..."):
            df_result = get_market_data(market_map[market_choice])
            
            st.subheader(f"✅ {market_choice} 수집 결과")
            st.write(f"총 {len(df_result)}개의 종목이 확인되었습니다.")
            
            # 데이터 표시
            st.dataframe(df_result, use_container_width=True)
            
            # CSV 다운로드 버튼
            csv = df_result.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="📥 결과 CSV 다운로드",
                data=csv,
                file_name=f"naver_finance_{market_choice}_face_value.csv",
                mime='text/csv',
            )
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
else:
    st.info("왼쪽 사이드바에서 시장을 선택한 후 '데이터 불러오기'를 눌러주세요.")
