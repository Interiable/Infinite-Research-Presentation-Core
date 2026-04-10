import os
import re
import asyncio
import markdown
from playwright.async_api import async_playwright

md_path = "/home/hgeon/gravity/LangAIAgent/backend/artifacts/9zsvx/00_Project_Recursive_Master_Report.md"
pdf_path = "/home/hgeon/gravity/LangAIAgent/backend/artifacts/9zsvx/00_Project_Recursive_Master_Report.pdf"

# Curated Table of Contents - manually written based on actual content analysis
CURATED_TOC = """## Table of Contents

### Step 1 — 시스템 인지 아키텍처 설계 (System Perception Architecture Design)
: Physical AI UX의 3대 핵심 기둥(ToM, LMA, UX 원칙)을 실현하기 위한 이중 경로(Dual-Path) 아키텍처의 초기 설계와 CPU-GPU 실시간 처리 구조를 정립합니다.

- **1.1** — 멀티모달 비전 인지 스택 선정 및 RTX 5090 하드웨어 프로파일링
  - 1.1.1: Face/Gaze/Emotion/Gesture 인식을 위한 SOTA 로컬 AI 모델(YOLOv8, L2CS-Net, HaMeR) 선정 및 TensorRT FP16 기반 성능 검증
  - 1.1.2: RTX 5090 아키텍처에서 VRAM 3.1GB, 병렬 추론 지연 1.6ms로 100Hz 제어 루프 충족 가능성을 수치 증명
  - 1.1.3: WFM(World Foundation Model)과 DMP 제어기 간 VRAM 충돌 없이 동시 실행하기 위한 비동기 멀티 레이트 처리 아키텍처(3-Tier)와 Zero-Copy 메모리 전송 설계

- **1.2** — 이중 경로 아키텍처 설계: 반응 계층(Fast) vs. 인지 계층(Slow)
  - 1.2.1: 1Hz Cognitive Layer(WFM/ToM)와 500Hz+ Reactive Layer(DMP)를 LMA 파라미터로 비동기 결합하는 Dual-Path Architecture의 수학적 설계
  - 1.2.2: 1000Hz 실시간 DMP 반사 제어를 위한 Fast Stream 아키텍처 — URDF 파싱 기반 CUDA Stream 격리 및 LMA-DMP 변조 수식 정의
  - 1.2.3: ToM 추론을 통해 사용자 감정·의도를 LMA 파라미터로 변환하는 Slow Stream의 Semantic Aggregation 설계 및 ROS2 인터페이스 명세
  - 1.2.4: 1kHz 물리 제어와 1Hz WFM 추론 데이터를 LMA 에너지 기반 Key-Frame 유지 방식으로 정렬하는 시간 동기화 및 LMA-Preserving Decimation Algorithm(LPDA) 설계

- **1.3** — ROS2 노드 아키텍처 및 커스텀 메시지 인터페이스 설계
  - 1.3.1: Fast Path(C++, 30~60Hz)와 Slow Path(Python, 0.5~1Hz)를 Perception Blackboard 노드로 융합하는 ROS2 이중 경로 노드 토폴로지 정의
  - 1.3.2: SpatialTarget, ToMState, LMAParams 등 Physical AI UX 동작을 위한 커스텀 ROS2 메시지 스키마 및 토픽 인터페이스 명세
  - 1.3.3: Fast Stream(Best Effort)과 Slow Stream(Reliable/Transient Local)의 Data Flow 특성에 맞는 QoS 프로파일 설계 및 Lock-Free 데이터 융합 모델

- **1.4** — 인지 계층 검증 및 지연 시간 이론 분석
  - 1.4.1: 시선 공유(Shared Gaze)와 살아있는 반응(Lifelike Reaction) UX 원칙에 대한 인지 계층 충족 여부를 수학적으로 검증
  - 1.4.2: 카메라 입력부터 ROS2 Topic 발행까지의 전체 단계별 이론적 지연 시간($T_{camera}$~$T_{DDS}$)을 수치 모델로 산출
  - 1.4.3: 100Hz WFM 지연을 500Hz DMP 제어가 감추는 비동기 Brain-Spine 동기화 모델과 URDF-Agnostic Fast Path C++ 구현 명세

---

### Step 2 — 다중 모달 인지 하드웨어 벤치마킹 (Multi-Modal Perception Hardware Benchmarking)
: 실 하드웨어(RTX 5090) 환경에서 비전·오디오·프로프리오셉션 데이터를 동시 처리할 때의 VRAM, FPS, 지연 시간을 정밀 프로파일링하고 병목을 제거합니다.

- **2.1** — 멀티모달 Human Perception 모델 선정 및 동시성 최적화
  - 2.1.1: 시각(Face/Gaze/Gesture)+음성(Whisper/Emotion) 인식을 위한 SOTA 로컬 모델 선정 및 URDF-Agnostic TF2 좌표 변환 통합 설계
  - 2.1.2: RTX 5090 32GB GDDR7에서 VRAM 할당, E2E 지연, FPS 및 64-DoF 로봇 스케일 가능성 벤치마크 결과 수치화
  - 2.1.3: "Elastic Buffer" 전략으로 Lock-Free 스트림 브리징을 구현하여 WFM-DMP 간 병목 없는 3-Tier 비동기 실행 아키텍처 설계

- **2.2** — 반응형·인지형 스트림 분기 아키텍처 설계
  - 2.2.1: ROS2 QoS(Best Effort vs. Reliable)로 Reactive Fast Stream과 Cognitive Slow Stream을 물리적으로 분기하는 아키텍처와 LMA-DMP 수학적 결합 모델
  - 2.2.2: 시선 벡터·공간 바운딩 박스 처리를 위한 Zero-Copy Fast Stream 및 1 Euro Filter 기반 LMA Flow 보존 신호 처리 파이프라인 명세
  - 2.2.3: 감정·의도 인식을 위해 Sliding Window 기반으로 다중 모달 데이터를 집약하고, LPDA로 WFM 입력을 5Hz로 데시메이션하는 Slow Stream 의미 처리 로직
  - 2.2.4: 1kHz 반응 데이터와 1Hz 인지 상태를 Lock-Free Ring Buffer 및 메시지 타임스탬프 정렬 알고리즘으로 동기화하는 시간 정렬 모듈

- **2.3** — ROS2 노드 토폴로지 및 커뮤니케이션 인터페이스 정의
  - 2.3.1: Dual-Path 인지 패러다임에서 Fast/Slow Path를 하나의 DMP 제어기로 매핑하고 URDF 동적 재구성을 지원하는 ROS2 노드 토폴로지 설계
  - 2.3.2: EmotionLMA, SharedGazeTarget, ToMIntent 등 실시간 스트림 무결성을 보장하는 커스텀 메시지 스키마 및 QoS 정책 매트릭스
  - 2.3.3: 시선(Gaze), 감정(Emotion), 신뢰도(Confidence) 필드 전용 커스텀 ROS2 메시지 인터페이스 정의 및 수학적 신뢰도 계산 모델

- **2.4** — 전체 파이프라인 지연 시간 분석 및 Fast Path 타이밍 최적화
  - 2.4.2: 센서 획득·버스 전송·OS·ROS2·DDS 레이어별 이론적 지연 시간을 정밀 분해하여 전체 End-to-End 지연 예산 산출
  - 2.4.3: Dual-Loop Phase Synchronization 알고리즘으로 WFM 지연을 보상하고 Fast Path의 DMP 변조를 1ms 이내로 유지하는 타이밍 최적화 아키텍처

---

### Step 3 — 사회적 상호작용 인지 파이프라인 설계 (Social Interaction Perception Pipeline)
: 실제 사람과의 사회적 상호작용을 위한 표정·시선·제스처 인식 파이프라인과, 이를 ROS2로 통합하는 메시지 스키마 및 QoS 정책을 심화 설계합니다.

- **3.1** — Face/Gaze/Emotion/Gesture 인식 파이프라인 심화 설계
  - 3.1.1: 미세 표정(HSEmotion), 3D 시선(L2CS-Net), 제스처(YOLOv8-Pose) 인식을 위한 SOTA 모델 파이프라인 및 URDF-Agnostic TF 통합 데이터 흐름
  - 3.1.2: RTX 5090/TensorRT FP16에서 5개 모델 병렬 추론 시 VRAM, 지연 시각, 텐서 차원 및 실행 가능성 벤치마크
  - 3.1.3: ROS2 Zero-Copy와 CUDA Stream 비동기 다중 추론, URDF-Agnostic 동적 카메라 캘리브레이션을 통합하는 동시성 실행 프레임워크

- **3.2** — 반응형·인지형 스트림 최적화 및 시간 정렬
  - 3.2.1: Cerebrum(Slow Path, WFM/ToM)과 Spinal Cord(Fast Path, DMP)를 ROS2 Action/Topic으로 연결하는 Dual-Path Architecture 상세 설계
  - 3.2.2: < 50ms 반응 데이터를 위한 Zero-Copy Transport, URDF Dynamic Memory Pooling, Executor Callback 격리 및 LMA 보간 지연 경계 수식화
  - 3.2.3: LMA 에너지 기반 Key-Frame 선택(LPDA), EKF 기반 관절 데이터 필터링, Savitzky-Golay Flow 추출, 멀티 모달 시간 정렬 알고리즘

- **3.3** — ROS2 노드 아키텍처·토픽 인터페이스·커스텀 메시지 정의
  - 3.3.1: FastReflex(C++)와 SlowCognitive(Python) 노드가 Fusion Node를 거쳐 DMP로 전달되는 ROS2 노드 그래프와 URDF-Agnostic 실행 엔진 설계
  - 3.3.2: 계층적 토픽 명명 규칙, 데이터 특성별 QoS 프로파일(Sensor Data/Reliable), DDS KeepAlive 튜닝 정책
  - 3.3.3: MultimodalPerception, CognitiveState, LMAModulation, UXPrincipleDirective, ExpressiveMotion.action 등 사회적 상호작용용 커스텀 메시지 스키마 설계

- **3.4** — 인지 계층 검증: 시선 공유 및 살아있는 반응 원칙 검증
  - 3.4.1: Shared Gaze와 Lifelike Reaction UX 원칙에 대한 인지 파이프라인의 이론적 충족 여부를 수학적으로 검증하고 ROS2 QoS 지표로 평가
  - 3.4.2: 인지 계층 각 단계별(카메라→추론→DDS) E2E 지연 예산 분해 및 WFM 지연 마스킹 전략 수식화
  - 3.4.3: URDF 제약 기반 Fast Path 반응 아키텍처, LMA-DMP 시간 상수 변조 수식, "Shared Gaze & Startle Reflex" UX 원칙의 물리적 구현 명세

---

### Step 4 — QoS·스트림 통합·인터페이스 심화 설계 (QoS, Stream Integration & Interface Engineering)
: Fast/Slow Stream의 QoS 정책, 커스텀 메시지 인터페이스, VRAM 최적화를 프로덕션 레벨에서 구체화하고 전체 지연 시간을 수학적으로 검증합니다.

- **4.1** — 로컬 AI 모델 최종 선정 및 추론 동시성 프레임워크
  - 4.1.1: 2026 기준 SOTA 로컬 모델(YOLOv11, GazeTR, EMOCLIP 등) 최종 선정, 3 Pillars 연동 방식 및 URDF-Agnostic ROS2 데이터 흐름 설계
  - 4.1.2: RTX 5090에서 모델별 VRAM·지연·FPS 프로파일링, 비동기 CUDA Stream 3-레인 실행 아키텍처, 100Hz 제어 루프 동기화 방식
  - 4.1.3: 5개 모델 병렬 추론 시 총 VRAM 6.35GB, Critical Path 지연 2.8ms 수학적 증명 및 VRAM 동적 할당 전략

- **4.2** — Reactive/Cognitive 스트림 최적화 및 Temporal Synchronization
  - 4.2.1: "Elastic Spine" 모델로 Fast/Slow Partition을 URDF-Agnostic Pipeline에 통합하고 LMA-DMP 수학적 결합 동기화 브릿지 설계
  - 4.2.2: < 50ms 반응형 Fast Stream의 LMA 반사 변조 수식, Physical AI UX 원칙 구현, URDF 기반 Safety Constraint 적용
  - 4.2.3: URDF-Agnostic Semantic Data Aggregation(SDA)과 Semantic Time-Warping Attention(STWA)으로 WFM Context Window를 생성하는 Slow Stream 로직
  - 4.2.4: Fast Stream($S_f$) 반응 필터링, Slow Stream($S_s$) FIR 필터링, 멀티 모달 시간 정렬, 감정 상태 업샘플링·보간 알고리즘

- **4.3** — ROS2 노드·QoS·커스텀 메시지 인터페이스 정의
  - 4.3.1: SlowCognitiveTomNode와 FastPerceptionReflexNode의 역할, Cross-Path LMA 파라미터 매핑, URDF-Agnostic 바인딩 메커니즘
  - 4.3.2: 이기종 데이터 스트림 분류, URDF 기반 동적 Deadline 할당 모델, LMA·UX 원칙 보장을 위한 지연 시간 제어 C++ 구현체
  - 4.3.3: Perception / Cognition / Modulation / Execution 4계층 인터페이스 메시지 정의 및 DMP 제어 명령을 위한 URDF-Agnostic Action 인터페이스

- **4.4** — 전체 시스템 검증: 지연 분석 및 Fast Path 최적화
  - 4.4.1: Shared Gaze와 Lifelike Reaction 원칙 충족을 위한 인지 계층 수학적 검증 및 ROS2 시스템 아키텍처 지연 검증
  - 4.4.2: 카메라($T_{cam}$)→전송($T_{trans}$)→ROS2($T_{acq}$)→AI 추론($T_{infer}$)→DDS 발행($T_{pub}$) 단계별 지연 예산 수치 산출
  - 4.4.3: Dual-Loop 인지-반응 패러다임, LMA-DMP 실시간 변조 수학 모델, Null-Space 투영을 통한 연속 UX 원칙 구현 및 Fast-Slow Blending

---

### Step 5 — 프로덕션 레벨 구현 청사진 (Production Implementation Blueprint)
: 전체 Physical AI UX 아키텍처를 실제 배포 가능한 ROS2 코드베이스로 구체화하고, 멀티 모달 데이터 융합·합성 전략을 완성합니다.

- **5.1** — SOTA 멀티모달 비전 모델 최종 선정 및 동시성 최적화
  - 5.1.1: 3 Pillars 정렬 기준으로 YOLOv8/GazeTR/HSEmotion 등 최종 확정, URDF-Agnostic 좌표 변환 아키텍처 및 Perception 데이터 흐름 설계
  - 5.1.2: RTX 5090 하드웨어 프로파일, 모델 스택 성능 매트릭스, 컨텍스트 벡터($C$) 수학적 정의, Critical Path 지연 분석($L_{crit}$)
  - 5.1.3: ROS2+CUDA 멀티 레이트 동시 실행 아키텍처, Pinned Memory 기반 VRAM 최적화 전략, 동시 실행 흐름도 및 최적화 지표 요약

- **5.2** — Fast/Slow Stream 최적화 및 멀티 모달 데이터 정렬
  - 5.2.2: < 50ms E2E 지연 예산 관리, 경량 Edge 비전 파이프라인, LMA-DMP 반응 엔진, Pinocchio 기반 URDF-Agnostic Fast Kinematics
  - 5.2.3: 다중 모달 데시메이션 알고리즘, 사용자 LMA 파라미터 추출기, WFM 프롬프트 JSON 직렬화, ROS2 구현 아키텍처
  - 5.2.4: 다중 주기 시간 동기화, Savitzky-Golay·EKF 데이터 필터링, 신뢰도 가중 멀티모달 융합 전략 및 URDF-Agnostic 데이터 흐름 요약

- **5.3** — System 1 & System 2 패러다임의 ROS2 노드·QoS 설계
  - 5.3.1: System 1(즉각적 반사, Fast)과 System 2(심층 인지, Slow)로 아키텍처를 분류하고 LMA 파라미터를 브릿지로 연결하는 URDF-Agnostic 동적 구성 파이프라인
  - 5.3.2: 3 Pillars 맞춤형 ROS2 QoS 프로파일(C++/rclcpp), Liveliness & Deadline 기반 UX Fallback, URDF 기반 동적 QoS 튜닝
  - 5.3.3: GazeTarget, EmotionState, ConfidenceField, ExpressiveCommand 등 최종 통합 제어 페이로드 커스텀 메시지 정의

- **5.4** — 전체 시스템 최종 지연 분석 및 Fast Path 타이밍 고도화
  - 5.4.1: Shared Gaze & Lifelike Reaction 원칙의 인지 계층 충족 여부 수학적 검증, ROS2 QoS 성능 지표
  - 5.4.2: 카메라→추론→의도 벡터화→DDS 발행 단계별 지연 예산 분해 및 Fast Path E2E 지연 합산
  - 5.4.3: Reactive LMA-DMP 변조의 수학적 형식화, Phase Coupling 타이밍 최적화, 인지 모델 동기화($\\Delta t_{sync}$), Null-Space UX 투영 및 QoS 명세

---

### Step 6 — 최종 아키텍처 검증 및 지연 최적화 (Final Architecture Verification & Latency Optimization)
: 완성된 Physical AI UX 아키텍처를 전체 시스템 수준에서 검증하고, 각 레이어의 지연 시간을 최적화하여 프로덕션 배포 준비를 마칩니다.

- **6.1** — 최종 비전 모델 스택 구성 및 동시성 VRAM 최적화
  - 6.1.1: 3 Pillars 기준 로컬 시각 인지 시스템 설계 요구사항, SOTA 모델 선정·역할 분류, URDF-Agnostic 다중 모달 데이터 융합 및 좌표 변환
  - 6.1.2: RTX 5090 Compute Infrastructure, 모델별 프로파일링, 파이프라인 타이밍 로직, 퍼셉션 출력 텐서 및 성능 벤치마크
  - 6.1.3: 비동기-동기 하이브리드 동시성 아키텍처, LMA-DMP 실시간 변조용 Latent Action Buffering, VRAM 동적 할당 전략

- **6.2** — 최종 Dual-Path 스트림 아키텍처 및 데이터 필터링·동기화
  - 6.2.1: Cognitive Slow Stream(LMA 파라미터 생성)과 Reactive Fast Stream(DMP 제어·UX 원칙 합성)을 URDF-Agnostic Engine으로 통합하는 최종 아키텍처
  - 6.2.2: 다중 지연 데이터 스트림 계층화, ROS2 QoS 엔지니어링, 교차 지연 동기화 및 LMA 보간 모델
  - 6.2.3: LMA·UX 보존 데이터 필터링, Cognitive-Motor Pipeline 멀티 Tier 데시메이션, ROS2 구현 시간 동기화 알고리즘 최종 정의

- **6.3** — 최종 ROS2 노드 아키텍처 및 Gaze/Emotion 스트림 인터페이스
  - 6.3.1: Dual-Path 노드 토폴로지, Perception Fusion Node 충돌 해결, Physical AI UX 원칙 매핑
  - 6.3.2: GazeVector.msg, EmotionState.msg 등 시선·감정 스트림 전용 커스텀 메시지 타입 명세 및 QoS 설정
  - 6.3.3: 실시간 Fast Path와 신뢰성 Slow Path의 Dual-Path 통신 모델, QoS 이벤트 기반 UX Principle 보장 아키텍처

- **6.4** — 최종 통합 시스템 검증: 인지 원칙 및 지연 시간 검증
  - 6.4.1: URDF-Agnostic 센서 프레임 매핑, Shared Gaze & Lifelike Reaction 검증 파이프라인, ToM/WFM 연동 검증
  - 6.4.2: E2E Perception 지연 모델($T_{perception}$), 단계별 심층 분석, Physical AI UX 함의 도출
  - 6.4.3: 반응형 시간 상수($\\tau$) 변조 수식화, LMA 기반 타이밍·Flow 변조, URDF 운동학 제약 적용, Fast Path ROS2 구현 및 UX 원칙 적용

---

### Step 7 — 완전 시스템 통합 및 수학적 정형화 (Complete System Integration & Mathematical Formalization)
: Physical AI UX 시스템 전체를 하나의 수학적으로 완결된 아키텍처로 통합하고, "Somatic Loop(반사)"와 "Psyche Loop(인지)"의 완전한 연결을 구현합니다.

- **7.1** — 최종 인지 모델 앙상블 및 시스템 병목 완화
  - 7.1.1: 모델 앙상블과 성능 행렬, 비동기 이중 구조(Bi-Cameral Mind) 실행 아키텍처, 상태 벡터 수학적 정의 및 PAD 매핑 로직
  - 7.1.2: RTX 5090 VRAM 할당 및 병렬 실행 지연 분석, Perception Interface 상태 벡터 정의
  - 7.1.3: LMA State Bridge(Shared Memory), "Keep-Alive" 생동감 엔진, "Thinking" 제스처 지연 마스킹, 동시 DMP 변조 수학적 구현, URDF 파싱 기반 하드웨어 독립 최적화

- **7.2** — 완전 Dual-Path 스트림 명세 및 신호 처리 최종 정의
  - 7.2.1: Reactive Fast Stream(반사 제어)과 Cognitive Slow Stream(의미 이해)의 아키텍처 분기 명세, 시간 동기화 및 상태 합성
  - 7.2.2: 반응형($I_h$) 신호 처리, 인지형($E_r$) 데시메이션·쓰로틀링, 멀티-레이트 스트림 시간 정렬
  - 7.2.3: 멀티 레이트 스트림 정렬, ZOH(영차 홀드)·버퍼링, Jitter 보상·보간, QoS 기반 동기화

- **7.3** — 최종 ROS2 노드 "뇌척수 모델" 및 토픽·QoS 명세
  - 7.3.1: Somatic Loop(척수, 반사)와 Psyche Loop(대뇌, 인지)로 구성된 4-Node 아키텍처(PerceptionAggregator, CortexWFM, SpinalCord, MotionSynthesis), LMA-DMP 수학적 정형화
  - 7.3.2: 전체 ROS2 토픽 네임스페이스, 실시간 스트림 QoS 정책, Hot Path 비동기 Executor 구현

---
"""

if not os.path.exists(md_path):
    print("MD file not found!")
    exit(1)

with open(md_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find end of current TOC
lines = content.split('\n')
toc_start = -1
toc_end = -1
in_toc = False

for i, line in enumerate(lines):
    if line.strip() == "## Table of Contents":
        toc_start = i
        in_toc = True
    elif in_toc and line.startswith("# ") and i > toc_start:
        # End of TOC (first non-TOC H1 section)
        toc_end = i
        break
    elif in_toc and line.startswith("<!-- "):
        toc_end = i
        break

if toc_start == -1:
    print("No existing TOC found. Inserting after title.")
    insert_at = 1  # After H1 title
    new_content = "\n".join(lines[:insert_at]) + "\n" + CURATED_TOC + "\n" + "\n".join(lines[insert_at:])
elif toc_end == -1:
    print("TOC found but no end detected.")
    exit(1)
else:
    print(f"Replacing TOC (lines {toc_start}-{toc_end})")
    new_content = "\n".join(lines[:toc_start]) + "\n" + CURATED_TOC + "\n" + "\n".join(lines[toc_end:])

with open(md_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Curated TOC written to Markdown.")
print("Converting to PDF...")

async def generate_pdf(markdown_content, output_pdf_path):
    html_content = markdown.markdown(markdown_content, extensions=['tables', 'fenced_code'])

    html_doc = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; padding: 40px; font-size: 14px; line-height: 1.6; color: #333; }}
    h1 {{ color: #1a1a1a; border-bottom: 2px solid #eaecef; padding-bottom: 0.3em; margin-bottom: 16px; margin-top: 24px; }}
    h2 {{ color: #2a2a2a; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 24px; margin-bottom: 16px; }}
    h3 {{ color: #444; margin-top: 24px; margin-bottom: 16px; }}
    pre {{ background-color: #f6f8fa; padding: 16px; border-radius: 6px; overflow: auto; white-space: pre-wrap; word-wrap: break-word; }}
    code {{ font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace; background-color: rgba(175, 184, 193, 0.2); padding: 0.2em 0.4em; border-radius: 6px; font-size: 85%; white-space: pre-wrap; word-wrap: break-word; }}
    pre code {{ background-color: transparent; padding: 0; white-space: pre-wrap; word-wrap: break-word; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 15px; margin-bottom: 15px; display: block; overflow: auto; }}
    th, td {{ border: 1px solid #d0d7de; padding: 6px 13px; }}
    th {{ background-color: #f6f8fa; font-weight: 600; }}
    tr:nth-child(2n) {{ background-color: #f6f8fa; }}
    blockquote {{ padding: 0 1em; color: #656d76; border-left: .25em solid #d0d7de; }}
    a {{ color: #0969da; text-decoration: none; }}
    </style>
    </head>
    <body>
    {html_content}
    </body>
    </html>
    """

    temp_html = output_pdf_path.replace(".pdf", "_temp.html")
    with open(temp_html, 'w', encoding='utf-8') as html_file:
        html_file.write(html_doc)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        file_url = f"file://{os.path.abspath(temp_html)}"
        await page.goto(file_url, wait_until="networkidle")
        await page.pdf(
            path=output_pdf_path,
            format="A4",
            print_background=True,
            margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"}
        )
        await browser.close()

    if os.path.exists(temp_html):
        os.remove(temp_html)

asyncio.run(generate_pdf(new_content, pdf_path))
print("PDF successfully generated.")
