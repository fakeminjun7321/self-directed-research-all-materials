# 2026 자율연구 최종 보고서 작업 공간

이 폴더의 Markdown·CSV가 보고서의 편집 가능한 원본이다. 최종 제출 형식이 HWPX이면 DOCX/PDF 초안을 검토한 뒤 한컴오피스에서 HWPX로 변환한다.

## 파일 역할

- `report_source.md`: 최종 본문 원본
- `REPORT_OUTLINE.md`: 작성 순서와 완료 조건
- `METHODS.md`: 재현 가능한 방법 상세
- `RESULTS_TABLE.csv`: 보고서에 사용할 검증된 수치
- `FIGURE_MANIFEST.csv`: 그림 출처·상태·캡션 관리
- `LIMITATIONS.md`: 과장 방지용 검증 한계
- `REFERENCE_INBOX.csv`: Zotero로 가져올 문헌 목록
- `references.bib`: 검증 완료 문헌만 넣는 BibTeX 파일

## 작성 원칙

1. `05_Report/comprehensive_report_2026-05-27.pdf`와 기존 그림은 50 ps workflow 연습 결과다.
2. 기존 RDF·MSD·diffusion 그림은 최종 물성 결론으로 사용하지 않는다.
3. `Implemented`, `Unit-verified`, `Physical-device-verified`, `Not verified / 미검증`을 구분한다.
4. 검증된 숫자는 `RESULTS_TABLE.csv`와 source artifact를 함께 갱신한다.
5. 그림은 `FIGURE_MANIFEST.csv`에 생성 스크립트와 원본 데이터를 기록한 뒤 사용한다.

## 초안 생성 예시

```bash
pandoc \
  report_source.md METHODS.md LIMITATIONS.md \
  --bibliography=references.bib \
  -o 자율연구_보고서_초안.docx
```

빈 `references.bib` 상태에서도 본문에 citation key가 없으면 DOCX 초안을 만들 수 있다. 인용을 추가하기 전에는 `REFERENCE_INBOX.csv`의 metadata를 Zotero나 DOI 원문에서 확인한다.
