# 문헌 근거와 현재 판단

## 조성 범위

Yoon 등은 C3mpyrFSI에 LiFSI를 0–3.2 mol/kg 첨가한 계의 물성을 측정했다. 현재 조성 환산값은 다음과 같다.

- L1P3: 1.081 mol/kg
- L1P2: 1.621 mol/kg
- L1P1: 3.243 mol/kg
- L2P1: 6.486 mol/kg
- L3P1: 9.729 mol/kg

따라서 L1P3, L1P2, L1P1은 직접 확인한 실험 범위 안 또는 경계에 있지만, L2P1과 L3P1은 그 범위를 크게 넘는다. 논문은 3.2 mol/kg 조성이 실온에서 혼화된다고 설명하지만, 고농도에서 유리 상태의 다중 Tg도 언급한다.

- Yoon et al., PCCP 2015: https://pubs.rsc.org/en/content/articlelanding/2015/cp/c4cp05333h
- Author version: https://pubs.rsc.org/en/content/getauthorversionpdf/c4cp05333h

## 밀도 기준

별도 Energy & Environmental Science 보충자료 Table S3에는 3.2 mol/kg LiFSI/C3mpyrFSI의 20 °C 밀도가 1.55 g/cc로 기재되어 있다. 이는 L1P1 근처 조성의 유용한 기준이지만 298 K의 정확한 목표값은 아니며, 다른 네 조성으로 그대로 확장할 수 없다.

- EES supporting information, Table S3: https://www.rsc.org/suppdata/d1/ee/d1ee02929k/d1ee02929k1.pdf

현재 1,400 kg/m³는 Packmol과 EM 가능성을 보는 공학적 시작점이다. 승인된 물리 목표 밀도로 간주하지 않는다.

## cutoff와 시스템 크기

GROMACS는 minimum-image convention 때문에 cutoff가 가장 짧은 box vector의 절반을 넘지 않아야 하며, 압력 결합 중 box가 줄어들 수 있으므로 단순 하한보다 여유가 필요하다고 설명한다.

- GROMACS 2026 documentation: https://manual.gromacs.org/current/manual-2026.0.pdf

대표 실행의 실제 EM TPR은 `rlist = 1.26 nm`였다. 단일 L1P1의 1,400 kg/m³ box는 2.4491 nm이므로 `2 × rlist = 2.52 nm`보다 작다. L1P1x2의 3.0857 nm box는 같은 기준보다 22.4% 크다. 이것이 분자 수 2배 후보를 먼저 시험한 직접 이유다.

## 전하 스케일링

비분극 force field에서 이온 전하를 줄이는 방식은 polarization을 평균장으로 근사하기 위해 널리 사용된다. 다만 Li salt가 섞인 다성분 이온성 액체에 같은 scale이 그대로 맞는지는 별도 문제다.

- TFSI 기반 Li-IL의 polarizable MD 비교: https://pubs.rsc.org/en/content/articlehtml/2016/cp/c5cp05111h
- C3mpyrFSI/NaFSI 유사계에서 0.7 scale을 사용한 연구: https://pubs.rsc.org/en/content/articlepdf/2023/ee/d3ee00864a

두 자료는 현재 0.75 값을 직접 검증하지 않는다. 따라서 이번 후보에서는 기존 연구 조건 보존을 위해 0.75를 유지했으며, 값을 최적화하거나 정답으로 확정하지 않았다.

## 현재 결정

- 기존 교수 전달 ZIP은 불변으로 유지한다.
- L1P1x2 1,400 kg/m³ 후보는 EM 기술 시험까지만 채택한다.
- NVT/NPT/production은 조성별 목표 밀도, 전하 스케일, 프로토콜 승인을 받은 뒤 진행한다.
- L2P1/L3P1은 298 K 상 상태와 조성 의도를 먼저 확인한다.
