import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

# 페이지 설정
st.set_page_config(page_title="주가 < 액면가 종목 추출기", layout="wide")

def get_filtered_market_data(market_code):
    """
    market_code: KOSPI=0, KOSDAQ=1
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
    }
    
    # 1. 마지막 페이지 번호 확인
    base_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={market_code}"
    res = requests.get(base_url, headers=headers)
    soup = BeautifulSoup(res.text, 'lxml')
    
    last_page_tag = soup.find('td', class_='pgRR')
    last_page = int(last_page_tag.a['href'].split('page=')[-1]) if last_page_tag else 1

    all_dfs = []
    
    # 스트림릿 상태 표시용 UI
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 2. 페이지별 크롤링 (액면가 필드 강제 포함)
    for page in range(1, last_page + 1):
        url = f"{base_url}&fieldIds=face_value&page={page}"
        res = requests.get(url, headers=headers)
        
        # [오류 해결] io.StringIO를 사용하여 HTML 문자열을 파일 객체로 변환
        df_list = pd.read_html(io.StringIO(res.text), encoding='euc-kr')
        df = df_list[1]
        
        # 데이터 정리: 종목명이 없는 행 및 불필요한 열 제거
        df = df.dropna(subset=['종목명'])
        df = df.loc[:, ~df.columns.str.contains('Unnamed')]
        
        all_dfs.append(df)
        
        # 상태 업데이트
        progress_bar.progress(page / last_page)
        status_text.text(f"데이터 수집 중... ({page}/{last_page} 페이지)")
        
    final_df = pd.concat(all_dfs, ignore_index=True)
    
    # 3. 데이터 전처리 (결측치 및 하이픈을 0으로 변환)
    # 엑셀 작업 시 오류 방지를 위해 '-' 기호를 0으로 대체합니다.
    final_df = final_df.replace('-', '0').fillna('0')
    
    if 'N' in final_df.columns:
        final_df = final_df.drop(columns=['N'])

    # 4. 필터링 로직 (현재가 < 액면가)
    # 비교를 위해 숫자형으로 변환 (콤마 제거 포함)
    cur_price_num = pd.to_numeric(final_df['현재가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    face_value_num = pd.to_numeric(final_df['액면가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # 필터 조건: 액면가가 0보다 크고, 현재가가 액면가보다 낮은 경우
    mask = (face_value_num > 0) & (cur_price_num < face_value_num)
    filtered_df = final_df[mask].reset_index(drop=True)
    
    # UI 정리
    status_text.empty()
    progress_bar.empty()
    
    return filtered_df

# 메인 UI
st.title("📊 주가 < 액면가 종목 리스트")
st.markdown("네이버 페이 증권 데이터를 기반으로 **현재주가가 액면가보다 낮은** 종목을 추출합니다.")

# 사이드바 설정
market_choice = st.sidebar.selectbox("시장 선택", ["KOSPI", "KOSDAQ"])
market_map = {"KOSPI": "0", "KOSDAQ": "1"}

if st.sidebar.button("데이터 분석 시작"):
    try:
        with st.spinner(f"{market_choice} 종목을 전수 조사 중입니다..."):
            result_df = get_filtered_market_data(market_map[market_choice])
            
            if not result_df.empty:
                st.subheader(f"✅ {market_choice} 분석 결과 (총 {len(result_df)}개 종목)")
                st.dataframe(result_df, use_container_width=True)
                
                # CSV 다운로드 버튼 (엑셀 한글 깨짐 방지를 위해 utf-8-sig 사용)
                csv = result_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    label="📥 분석 결과 CSV 다운로드",
                    data=csv,
                    file_name=f"low_face_value_{market_choice}.csv",
                    mime='text/csv',
                )
            else:
                st.info(f"{market_choice} 시장에 현재 조건에 해당하는 종목이 없습니다.")
                
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
else:
    st.info("왼쪽 사이드바에서 검색을 실행해 주세요.")
