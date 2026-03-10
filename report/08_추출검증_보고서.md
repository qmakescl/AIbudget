# 예산 데이터 재추출 검증 리포트

> 생성일: 2026-03-09 | 추출 방법: pdfplumber(1차) + PyMuPDF(2~3차)

---

## 1. 전체 통계

| 항목 | 값 |
|------|---|
| 총 사업수 | 533건 |
| budget_2026 추출 성공 | 533건 (100.0%) |
| 신규사업 | 188건 (35.3%) |
| 검증 전체 통과 (OK) | 491건 (92.1%) |
| V2 산술 불일치 | 38건 |
| V3 비율 불일치 | 31건 |
| V5 비율 범위 이상 | 0건 |
| 2026 총 예산 (백만원) | 27,609,325 |
| 2025 총 예산 (백만원) | 21,665,144 |
| 순증감 (백만원) | +5,944,181 |

### 추출 방법 분포

| 방법 | 건수 |
|------|-----|
| pdfplumber | 525 |
| pymupdf_pass1 | 8 |

---

## 2. 부처별 요약

| 부처 | 사업수 | OK | 경고 |
|------|------|------|------|
| 감사원 | 1 | 1 | 0 |
| 개인정보보호위원회 | 3 | 3 | 0 |
| 경찰청 | 11 | 10 | 1 |
| 고용노동부 | 11 | 6 | 5 |
| 과학기술정보통신부 | 192 | 181 | 11 |
| 관세청 | 1 | 1 | 0 |
| 교육부 | 11 | 11 | 0 |
| 국가데이터처 | 5 | 5 | 0 |
| 국가유산청 | 1 | 1 | 0 |
| 국민권익위원회 | 1 | 1 | 0 |
| 국방부 | 7 | 7 | 0 |
| 국세청 | 3 | 3 | 0 |
| 국토교통부 | 40 | 37 | 3 |
| 금융위원회 | 3 | 3 | 0 |
| 기상청 | 3 | 3 | 0 |
| 기획예산처 | 1 | 0 | 1 |
| 기후에너지환경부 | 33 | 23 | 10 |
| 농림축산식품부 | 9 | 9 | 0 |
| 농촌진흥청 | 8 | 8 | 0 |
| 대법원 | 2 | 2 | 0 |
| 문화체육관광부 | 12 | 12 | 0 |
| 방송미디어통신위원회 | 4 | 4 | 0 |
| 방위사업청 | 1 | 1 | 0 |
| 법무부 | 5 | 4 | 1 |
| 법제처 | 1 | 1 | 0 |
| 병무청 | 1 | 1 | 0 |
| 보건복지부 | 20 | 20 | 0 |
| 산림청 | 10 | 9 | 1 |
| 산업통상부 | 51 | 48 | 3 |
| 소방청 | 3 | 3 | 0 |
| 식품의약품안전처 | 6 | 5 | 1 |
| 외교부 | 1 | 1 | 0 |
| 우주항공청 | 4 | 4 | 0 |
| 인사혁신처 | 2 | 2 | 0 |
| 조달청 | 1 | 1 | 0 |
| 중소벤처기업부 | 16 | 16 | 0 |
| 지식재산처 | 1 | 0 | 1 |
| 질병관리청 | 4 | 4 | 0 |
| 해양경찰청 | 5 | 5 | 0 |
| 해양수산부 | 27 | 24 | 3 |
| 행정안전부 | 12 | 11 | 1 |

---

## 3. 검증 경고/실패 항목

| 부처 | 사업명 | 추출방법 | 플래그 |
|------|------|------|------|
| 경찰청 | 불법 마약류 대응을 위한 현장기술 개발(R&D) | pdfplumber | V3:RATE_MISMATCH(expected=228.8%,got=222.8%) |
| 고용노동부 | 내일배움카드(일반) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=31164,got=47164)|V3:RATE_MIS |
| 고용노동부 | 노동위원회정보화운영(정보화) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=-1650,got=-4317)|V3:RATE_MIS |
| 고용노동부 | 일자리정보플랫폼 기반 AI 고용서비스 지원(정보화) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=2094,got=3594)|V3:RATE_MISMA |
| 고용노동부 | 직업능력개발담당자양성 및 훈련매체개발 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=3192,got=6302)|V3:RATE_MISMA |
| 고용노동부 | 취약노동자지원 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=-1194,got=9356)|V3:RATE_MISM |
| 과학기술정보통신부 | AI최고급신진연구자지원사업(R&D) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=25000,got=28000)|V3:RATE_MIS |
| 과학기술정보통신부 | K-Health 국민의료 AI서비스 및 산업생태계 구축 | pdfplumber | V3:RATE_MISMATCH(expected=-33.3%,got=33.3%) |
| 과학기술정보통신부 | 광주과학기술원 연구 운영비 지원(R&D) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=19226,got=22976)|V3:RATE_MIS |
| 과학기술정보통신부 | 디지털 질서 기반 구축 및 글로벌 확산 지원 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=21236,got=21886)|V3:RATE_MIS |
| 과학기술정보통신부 | 디지털역량강화교육 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=-24563,got=-17983)|V3:RATE_M |
| 과학기술정보통신부 | 디지털전문·융합인재양성 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=35436,got=40436)|V3:RATE_MIS |
| 과학기술정보통신부 | 생성AI선도인재양성(R&D) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=18300,got=21800)|V3:RATE_MIS |
| 과학기술정보통신부 | 울산과학기술원 연구 운영비 지원(R&D) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=28629,got=36129)|V3:RATE_MIS |
| 과학기술정보통신부 | 의료AI혁신생태계조성(닥터앤서3.0) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=4100,got=8100)|V3:RATE_MISMA |
| 과학기술정보통신부 | 제조업 AI융합 기반 조성 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=-4125,got=-125)|V3:RATE_MISM |
| 과학기술정보통신부 | 한국과학기술원 연구 운영비 지원(R&D) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=63721,got=78721)|V3:RATE_MIS |
| 국토교통부 | 스마트시티확산사업 | pdfplumber | V3:RATE_MISMATCH(expected=62.4%,got=82.6%) |
| 국토교통부 | 자율자동차 상용화 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=75,got=475)|V3:RATE_MISMATCH |
| 국토교통부 | 자율주행글로벌혁신클러스터연구개발사업(R&D) | pdfplumber | V4:NEW_BUT_HAS_2025_BUDGET |
| 기획예산처 | 디지털예산회계시스템 운영(정보화) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=1171,got=1547)|V3:RATE_MISMA |
| 기후에너지환경부 | 광역상수도 안정화 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=15009,got=-9929) |
| 기후에너지환경부 | 대기오염측정망 구축·운영 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=-4148,got=826) |
| 기후에너지환경부 | 무탄소에너지핵심기술개발사업(R&D) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=9645,got=10870) |
| 기후에너지환경부 | 물산업정책 및 국제협력 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=1877,got=2877) |
| 기후에너지환경부 | 사업장 미세먼지 관리사업 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=10474,got=15125) |
| 기후에너지환경부 | 상수도정보화시스템구축(정보화) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=-214,got=-514) |
| 기후에너지환경부 | 생물다양성 보전 및 관리 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=0,got=-71) |
| 기후에너지환경부 | 수문조사시설 설치 및 개선 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=82350,got=3866)|V3:RATE_MISM |
| 기후에너지환경부 | 환경정보화기반구축(정보화) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=64,got=-116) |
| 기후에너지환경부 | 환경행정 정보서비스 구축(정보화) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=1110,got=411) |
| 법무부 | 첨단범죄및디지털수사(정보화) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=12142,got=2424)|V3:RATE_MISM |
| 산림청 | 산불방지대책 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=-16122,got=27508)|V3:RATE_MI |
| 산업통상부 | 대한무역투자진흥공사 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=6823,got=12139)|V3:RATE_MISM |
| 산업통상부 | 산업기술국제협력(R&D) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=22346,got=23346)|V3:RATE_MIS |
| 산업통상부 | 산업단지환경조성 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=22442,got=78542)|V3:RATE_MIS |
| 식품의약품안전처 | 식의약품 안전정보체계 선진화(정보화) | pymupdf_pass1 | V2:ARITHMETIC_MISMATCH(expected=3919,got=5227)|V3:RATE_MISMA |
| 지식재산처 | 지식재산 활용(사업화, 거래, 평가) 지원 | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=9845,got=7845)|V3:RATE_MISMA |
| 해양수산부 | 순환적응형연안침식관리기술개발(R&D) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=6690,got=1012)|V3:RATE_MISMA |
| 해양수산부 | 유수식 디지털양식 혁신기술개발(R&D) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=2240,got=2440) |
| 해양수산부 | 한국해양과학기술원운영지원(R&D) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=4191,got=5041)|V3:RATE_MISMA |
| 행정안전부 | 범정부 인공지능 공통기반 구현(정보화) | pdfplumber | V2:ARITHMETIC_MISMATCH(expected=1979,got=7371)|V3:RATE_MISMA |

---

## 4. 부처별 데이터 형식 변이 카탈로그

| 부처 | 열 구조 | 비고 |
|------|------|------|
| 감사원 | 8열 | - |
| 개인정보보호위원회 | 8열 | 신규마커 |
| 경찰청 | 7/8열 | 신규마커 |
| 고용노동부 | 7/8열 | 신규마커 |
| 과학기술정보통신부 | 8열 | 신규마커 |
| 관세청 | 8열 | - |
| 교육부 | 8열 | 신규마커 |
| 국가데이터처 | 8열 | - |
| 국가유산청 | 8열 | 신규마커 |
| 국민권익위원회 | 8열 | - |
| 국방부 | 7/8열 | - |
| 국세청 | 8열 | - |
| 국토교통부 | 6/7/8열 | 신규마커 |
| 금융위원회 | 8열 | 신규마커 |
| 기상청 | 8열 | - |
| 기획예산처 | 8열 | - |
| 기후에너지환경부 | 8열 | 신규마커 |
| 농림축산식품부 | 7/8열 | 신규마커 |
| 농촌진흥청 | 7열 | 신규마커 |
| 대법원 | 7/8열 | - |
| 문화체육관광부 | 8열 | 신규마커 |
| 방송미디어통신위원회 | 8열 | 신규마커 |
| 방위사업청 | 8열 | 신규마커 |
| 법무부 | 8열 | - |
| 법제처 | 8열 | - |
| 병무청 | 8열 | - |
| 보건복지부 | 8열 | 신규마커 |
| 산림청 | 8열 | 신규마커 |
| 산업통상부 | 8열 | 신규마커 |
| 소방청 | 7열 | 신규마커 |
| 식품의약품안전처 | 7열 | 신규마커 |
| 외교부 | 8열 | - |
| 우주항공청 | 8열 | 신규마커 |
| 인사혁신처 | 7열 | - |
| 조달청 | 8열 | - |
| 중소벤처기업부 | 8열 | 신규마커 |
| 지식재산처 | 8열 | - |
| 질병관리청 | 8열 | 신규마커 |
| 해양경찰청 | 8열 | 신규마커 |
| 해양수산부 | 8열 | 신규마커 |
| 행정안전부 | 8열 | 신규마커 |

---

Q의 지침의 따라 Claude Code - claude-opus-4-6이 2026-03-09에 생성했습니다.