# 안경 (가칭) — Design Document

> **"Document in, Structured JSON out. Locally. With your schema."**
> 작성일: 2026-03-12 | 상태: Phase 5 진행 중 (5-1~5-3 완료, 217 tests, 배치처리+에러처리+문서화)
> 코드네임: **안경** | 패키지명: `docpick` (PyPI)
> 경로: `~/GitHub/glyph/`

---

## 1. 프로젝트 개요

### 1.1 한 줄 정의

경량 OCR + 로컬 LLM 기반의 **스키마 기반 문서 구조화 추출** 오픈소스 라이브러리.

### 1.2 왜 만드는가

| 기존 도구 | 한계 |
|-----------|------|
| PaddleOCR, Surya, EasyOCR | 텍스트만 추출. 구조화 JSON까지 안 감 |
| Docling, MinerU, Marker | PDF→마크다운. 커스텀 스키마 JSON 추출은 beta/불완전 |
| AWS Textract, Google Doc AI | 클라우드 종속, 건당 과금 |
| Unstract, Documind | 무겁거나 OpenAI 종속 |

**빈자리**: `pip install` → 문서 넣으면 → 사용자 정의 스키마에 맞는 JSON이 나오는 → **로컬 LLM 기반** → **과금 제로** 솔루션.

### 1.3 타겟 사용자

1. **엔터프라이즈 개발자** — 송장/무역서류 자동화 파이프라인 구축
2. **AI 엔지니어** — 문서 데이터 전처리 (RAG, fine-tuning)
3. **스타트업** — 클라우드 OCR API 비용 절감 (건당 $0.01 → $0)
4. **연구자** — 논문/보고서 구조화 추출

---

## 2. 핵심 설계 원칙

1. **Schema-First** — 스키마가 추출을 주도. 스키마 없이도 동작하지만, 스키마가 있으면 정확도가 극적으로 향상
2. **Local-First** — 클라우드 API 없이 완전 로컬 동작. 외부 LLM은 선택적 fallback
3. **Pluggable** — OCR 엔진, LLM 프로바이더 교체 가능
4. **Battery-Included** — 주요 엔터프라이즈 문서 스키마 내장 (Invoice, B/L, Receipt 등)
5. **Apache 2.0 Only** — 모든 의존성 Apache 2.0 / MIT. GPL/AGPL 배제
6. **Multilingual** — 한국어/영어/일본어 1st-class

---

## 3. 아키텍처

### 3.1 파이프라인 구조

```
┌───────────────────────────────────────────────────────────────────┐
│                         Docpick Pipeline                            │
│                                                                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐  │
│  │ Document  │   │   OCR    │   │   LLM    │   │  Validator   │  │
│  │  Loader   │──▶│  Engine  │──▶│ Extractor│──▶│  (optional)  │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘  │
│       │              │              │                │            │
│  PDF/이미지      텍스트+좌표     스키마 기반        체크디짓       │
│  멀티페이지      +confidence     JSON 구조화        합계 검증     │
│  자동 감지       자동 엔진선택   프롬프트 생성       교차 참조     │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    Structured JSON Output
                    + field-level confidence
                    + validation results
```

### 3.2 2-Tier OCR 전략

```
Tier 1: 경량 OCR (CPU, 빠름, 90% 트래픽)
  ├── PaddleOCR v5 (기본값, 52M params)
  └── EasyOCR (한국어 특화 시)

Tier 2: VLM OCR (GPU, 정밀, 복잡 문서)
  ├── PaddleOCR-VL-1.5 (0.9B, Apache 2.0, 109개 언어)
  ├── GOT-OCR2.0 (580M, Interactive OCR)
  └── 사용자 VLM (Qwen-VL, InternVL 등 OpenAI-compatible)

자동 선택 로직:
  if GPU available AND (confidence < threshold OR complex_layout):
      use Tier 2
  else:
      use Tier 1
```

### 3.3 LLM 구조화 추출

```python
# 스키마 기반 프롬프트 자동 생성
ocr_text = "Invoice No: INV-2026-001\nDate: 2026-03-12\nAmount: $12,450.00\n..."

prompt = f"""Extract structured data from this document text.
Output must conform to this JSON Schema:
{schema.json_schema()}

Document text:
{ocr_text}

Output ONLY valid JSON:"""

# LLM 프로바이더 (교체 가능)
├── vLLM (OpenAI-compatible, 로컬 GPU)
├── Ollama (로컬 CPU/GPU)
├── OpenAI API (fallback)
└── 커스텀 (any OpenAI-compatible endpoint)
```

---

## 4. 모듈 설계

### 4.1 패키지 구조

```
src/docpick/                       # 34 Python files
├── __init__.py                    # Public API exports
├── batch.py                       # BatchProcessor — asyncio 병렬 배치 처리
├── cli.py                         # CLI (extract, ocr, batch, validate, schemas, config)
├── core/
│   ├── __init__.py
│   ├── pipeline.py                # DocpickPipeline — 메인 오케스트레이터 (OCR fallback, 에러 추적)
│   ├── document.py                # DocumentLoader — PDF/이미지 로딩
│   ├── result.py                  # ExtractionResult — 결과 데이터 클래스 (+errors 필드)
│   └── config.py                  # DocpickConfig — 설정 관리
├── ocr/
│   ├── __init__.py                # OCREngine, AutoEngine, get_engine exports
│   ├── base.py                    # OCREngine ABC
│   ├── paddle.py                  # PaddleOCR backend (Tier 1)
│   ├── easyocr_engine.py          # EasyOCR backend (Tier 1)
│   ├── got.py                     # GOT-OCR2.0 backend (Tier 2, 580M)
│   ├── vlm.py                     # VLM OCR (Tier 2, OpenAI-compatible)
│   └── auto.py                    # AutoEngine — 2-Tier 자동 선택 + fallback
├── llm/
│   ├── __init__.py
│   ├── base.py                    # LLMProvider ABC (max_retries 지원)
│   ├── vllm_provider.py           # vLLM + Ollama providers (JSON 재시도)
│   └── prompt.py                  # 스키마→프롬프트 변환 + parse_llm_json (4단계 파싱)
├── schemas/                       # 8 built-in schemas
│   ├── __init__.py                # All schema exports
│   ├── base.py                    # DocumentSchema + SchemaRegistry
│   ├── invoice.py                 # Invoice / 세금계산서 (범용)
│   ├── receipt.py                 # Receipt
│   ├── bill_of_lading.py          # B/L (Ocean/Air/Multimodal)
│   ├── purchase_order.py          # Purchase Order
│   ├── certificate.py             # Certificate of Origin
│   ├── bank_statement.py          # Bank Statement
│   ├── kr_tax_invoice.py          # 한국 전자세금계산서 (전용)
│   └── id_document.py             # ID Document (MRZ)
├── validation/
│   ├── __init__.py                # All validation exports
│   ├── base.py                    # ValidationRule ABC + Validator
│   ├── checksum.py                # 5 algorithms (kr_biz, luhn, iso6346, awb, iban)
│   ├── rules.py                   # 6 rules (Sum, Date, Required, FieldEq, Range, Regex)
│   └── cross_document.py          # CrossDocumentValidator (교차 문서 검증)

tests/unit/                        # 15 files, 217 tests
```

### 4.2 핵심 클래스

#### DocpickPipeline (메인 진입점)

```python
from docpick import DocpickPipeline
from docpick.schemas import InvoiceSchema

# 기본 사용
pipeline = DocpickPipeline()
result = pipeline.extract("invoice.pdf", schema=InvoiceSchema)
print(result.data)        # {"invoice_number": "INV-2026-001", ...}
print(result.confidence)  # {"invoice_number": 0.97, ...}
print(result.validation)  # {"is_valid": True, "errors": [], ...}

# 커스텀 스키마
from pydantic import BaseModel

class MyDocument(BaseModel):
    title: str
    date: str
    total_amount: float
    items: list[dict]

result = pipeline.extract("document.png", schema=MyDocument)

# 스키마 없이 (자유 추출)
result = pipeline.extract("document.pdf")
print(result.text)        # OCR 텍스트
print(result.markdown)    # 구조화된 마크다운

# VLM 직접 추출 (이미지→JSON, OCR 스킵)
result = pipeline.extract("document.png", schema=InvoiceSchema, mode="vlm")
```

#### OCREngine ABC

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class OCRResult:
    text: str                          # 전체 텍스트
    blocks: list[TextBlock]            # 블록 단위 (텍스트+좌표+confidence)
    tables: list[Table] | None         # 테이블 (감지 시)
    layout: LayoutInfo | None          # 레이아웃 정보
    metadata: dict                     # 엔진별 메타데이터

@dataclass
class TextBlock:
    text: str
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 (normalized 0~1)
    confidence: float                         # 0.0~1.0
    page: int
    block_type: str                           # "text", "title", "table", "figure"

class OCREngine(ABC):
    @abstractmethod
    def recognize(self, image: Image | Path, languages: list[str] = None) -> OCRResult:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @property
    @abstractmethod
    def requires_gpu(self) -> bool:
        ...

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        ...
```

#### LLMProvider ABC

```python
class LLMProvider(ABC):
    @abstractmethod
    def extract_fields(
        self,
        text: str,
        schema: type[BaseModel],
        context: dict | None = None,    # 좌표, confidence 등 부가 정보
        max_retries: int = 1,           # JSON 파싱 실패 시 재시도 횟수
    ) -> dict:
        """OCR 텍스트에서 스키마에 맞는 필드를 추출"""
        ...

    @abstractmethod
    def extract_from_image(
        self,
        image_base64: str,
        schema: type[BaseModel],
        max_retries: int = 1,
    ) -> dict:
        """VLM 직접 추출 (이미지→JSON)"""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...
```

#### DocumentSchema (내장 스키마 예시)

```python
from pydantic import BaseModel, Field
from docpick.schemas.base import DocumentSchema
from docpick.validation import CheckDigit, SumEquals

class InvoiceLineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    amount: float | None = None
    tax_rate: float | None = None

class InvoiceSchema(DocumentSchema):
    """Universal Invoice / Tax Invoice schema"""
    # 메타
    document_type: str = "invoice"

    # 헤더
    invoice_number: str
    invoice_date: str
    due_date: str | None = None
    currency: str | None = Field(None, description="ISO 4217 currency code")
    po_number: str | None = None

    # 공급자
    vendor_name: str
    vendor_address: str | None = None
    vendor_tax_id: str | None = Field(None, description="사업자등록번호 or Tax ID")

    # 구매자
    customer_name: str
    customer_address: str | None = None
    customer_tax_id: str | None = None

    # 라인 아이템
    line_items: list[InvoiceLineItem] = []

    # 합계
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float

    # 검증 규칙
    class ValidationRules:
        rules = [
            SumEquals("line_items.amount", "subtotal"),
            SumEquals(["subtotal", "tax_amount"], "total_amount"),
            CheckDigit("vendor_tax_id", algorithm="kr_business_number"),
        ]
```

### 4.3 CLI 인터페이스

```bash
# 기본 추출
docpick extract invoice.pdf --schema invoice
docpick extract receipt.jpg --schema receipt --output result.json

# 커스텀 스키마 (JSON Schema 파일 경로 직접 지정)
docpick extract document.pdf --schema my_schema.json

# 스키마 없이 OCR만
docpick ocr document.pdf --format markdown
docpick ocr document.pdf --format text

# 배치 처리
docpick batch ./invoices/ --schema invoice --output ./results/

# 엔진/프로바이더 지정
docpick extract doc.pdf --schema invoice --ocr paddle --llm vllm
docpick extract doc.pdf --schema invoice --ocr vlm --llm ollama

# 내장 스키마 목록
docpick schemas list
docpick schemas show invoice

# 검증만
docpick validate result.json --schema invoice

# 설정
docpick config set ocr.engine paddle
docpick config set llm.provider vllm
docpick config set llm.base_url http://localhost:30000/v1
docpick config set llm.model Qwen/Qwen3.5-32B-AWQ
```

---

## 5. 내장 스키마 목록 (8종 구현 완료)

| 스키마 | 필드 수 | 검증 규칙 | 상태 |
|--------|---------|----------|------|
| `invoice` | 20+ | 합계×2, 날짜, 사업자번호×2, 필수×3 | ✅ |
| `receipt` | 15+ | 합계×2, 사업자번호, 필수×2 | ✅ |
| `bill_of_lading` | 30+ | ISO 6346, HS코드, 중량/개수 합계, 날짜, 통화, 필수×5 | ✅ |
| `purchase_order` | 20+ | 합계×2, 날짜, 통화, 필수×4 | ✅ |
| `certificate_of_origin` | 15+ | ISO 3166 alpha-2×3, 필수×3 | ✅ |
| `bank_statement` | 10+거래 | IBAN mod97, 기간 날짜, 필수×3 | ✅ |
| `kr_tax_invoice` | 25+ | 사업자번호×2, 공급가액+세액+합계 3중 합계, 필수×6 | ✅ |
| `id_document` | 15+ | MRZ, ISO 3166 alpha-3×2, 성별 코드, 날짜×2, 필수×4 | ✅ |

---

## 6. 검증 시스템 (구현 완료)

### 6.1 체크디짓 알고리즘 (5종)

```python
CheckDigitRule("vendor_tax_id", algorithm="kr_business_number")   # 한국 사업자등록번호 10자리
CheckDigitRule("card_number", algorithm="luhn")                    # 카드번호 Luhn
CheckDigitRule("container_number", algorithm="iso_6346")           # 컨테이너 ISO 6346
CheckDigitRule("awb_number", algorithm="awb_mod7")                 # AWB 항공화물 Modulus 7
CheckDigitRule("iban", algorithm="iban_mod97")                     # IBAN Modulus 97
```

### 6.2 교차 필드 검증 (6종)

```python
SumEqualsRule("line_items.amount", "subtotal")                     # 합계 검증 (배열 집계 지원)
SumEqualsRule(["subtotal", "tax_amount"], "total_amount")          # 다중 소스 합계
DateBeforeRule("invoice_date", "due_date")                         # 날짜 순서
RequiredFieldRule("invoice_number")                                # 필수 필드 (warning)
FieldEqualsRule("bl.total_packages", "pl.total_packages")          # 두 필드 일치
RangeRule("total", min_val=0, max_val=1000000)                     # 숫자 범위
RegexRule("currency", r"^[A-Z]{3}$", "ISO 4217 currency")         # 정규식 패턴
```

### 6.3 교차 문서 검증 (CrossDocumentValidator)

```python
from docpick.validation import CrossDocumentValidator, create_trade_document_validator

# 프리셋: Invoice ↔ B/L ↔ Packing List ↔ Certificate of Origin
validator = create_trade_document_validator()

# 커스텀 규칙 추가
validator.add_mapping("invoice", "total", "lc", "amount", "less_than_or_equal")

result = validator.validate({
    "invoice": invoice_data,
    "bl": bl_data,
    "packing_list": pl_data,
    "certificate": co_data,
})
# result.is_valid, result.errors, result.checks_applied
```

### 6.4 검증 결과

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]
    rules_applied: int
    rules_passed: int

@dataclass
class CrossDocumentResult:
    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]
    checks_applied: int
    checks_passed: int
```

---

## 7. 설정 체계

### 7.1 설정 파일 (~/.docpick/config.yaml)

```yaml
# OCR 설정
ocr:
  engine: auto                    # auto | paddle | easyocr | got | vlm
  languages: [ko, en]            # 기본 언어
  gpu: auto                      # auto | true | false
  confidence_threshold: 0.7      # Tier 2 전환 임계값

# LLM 설정
llm:
  provider: vllm                  # vllm | ollama | openai
  base_url: http://localhost:30000/v1
  model: Qwen/Qwen3.5-32B-AWQ
  temperature: 0.0
  max_tokens: 4096
  timeout: 30

# VLM 직접 추출 설정
vlm:
  enabled: false
  base_url: http://localhost:8081/v1
  model: Qwen/Qwen3-VL-4B

# 출력 설정
output:
  format: json                    # json | csv | markdown
  include_confidence: true
  include_bbox: false
  pretty_print: true

# 검증 설정
validation:
  enabled: true
  strict: false                   # true: error → exception, false: error → warning
```

### 7.2 환경변수 오버라이드

```bash
DOCPICK_OCR_ENGINE=paddle
DOCPICK_LLM_PROVIDER=ollama
DOCPICK_LLM_BASE_URL=http://localhost:11434
DOCPICK_LLM_MODEL=qwen3.5:7b
```

---

## 8. 의존성

### 8.1 Core (필수)

| 패키지 | 용도 | 라이선스 |
|--------|------|---------|
| `pydantic` >= 2.0 | 스키마, 검증, 설정 | MIT |
| `Pillow` | 이미지 처리 | MIT-CMU |
| `pypdfium2` | PDF→이미지 변환 | Apache 2.0 |
| `httpx` | LLM API 호출 | BSD |
| `pyyaml` | 설정 파일 | MIT |
| `click` | CLI | BSD |
| `rich` | CLI 출력 | MIT |

### 8.2 OCR Backends (선택적)

| 패키지 | 설치 | 라이선스 |
|--------|------|---------|
| `paddleocr` + `paddlepaddle` | `pip install docpick[paddle]` | Apache 2.0 |
| `easyocr` | `pip install docpick[easyocr]` | Apache 2.0 |
| `transformers` (GOT-OCR) | `pip install docpick[got]` | Apache 2.0 |

### 8.3 LLM Providers (선택적)

| 프로바이더 | 추가 의존성 | 비고 |
|-----------|-----------|------|
| vLLM | 없음 (httpx로 OpenAI-compatible 호출) | 기본값 |
| Ollama | 없음 (httpx) | |
| OpenAI | `openai` | fallback |

---

## 9. 기술 결정

### 9.1 PDF 라이브러리

- ~~PyMuPDF~~ (AGPL) → **pypdfium2** (Apache 2.0) 사용
- PDF→이미지 변환 + 텍스트 기반 PDF 감지

### 9.2 OCR 기본 엔진

- **PaddleOCR** 기본값 (72k stars, Apache 2.0, 111개 언어)
- PaddlePaddle 프레임워크 종속이 단점이나, 생태계 규모와 라이선스가 결정적
- EasyOCR는 한국어 전용 모델이 있어 보조 옵션

### 9.3 LLM 프롬프트 전략

```
[System]
You are a document data extraction assistant.
Extract fields from OCR text according to the provided JSON schema.
Output ONLY valid JSON. Do not include explanations.
If a field is not found, use null.

[User]
## JSON Schema
{schema_json}

## OCR Text
{ocr_text}

## Additional Context (optional)
- Document language: {language}
- Low confidence regions: {low_conf_regions}
- Table data: {table_text}
```

### 9.4 VLM 직접 추출 모드

복잡한 문서(표가 많거나, 스캔 품질이 낮은 경우)에서는 OCR 단계를 건너뛰고 VLM이 이미지에서 직접 JSON을 추출:

```python
result = pipeline.extract("complex_table.png", schema=InvoiceSchema, mode="vlm")
# VLM이 이미지를 직접 보고 스키마에 맞는 JSON 생성
```

---

## 10. 에러 처리 & 배치 처리

### 10.1 파이프라인 에러 처리

```
Document Load 실패 → ExtractionResult(errors=["Document load failed: ..."])
OCR 엔진 실패 → 자동 fallback (paddle → easyocr)
           └→ 전부 실패 시 → OCRResult(text="", engine="none") + errors 기록
LLM JSON 파싱 실패 → correction prompt로 자동 재시도 (max 1회)
           └→ parse_llm_json 4단계 전략:
              1. 직접 파싱
              2. { } 경계 추출
              3. trailing comma 수정
              4. 추출 + 수정 조합
           └→ 재시도도 실패 → data={}, errors 기록 (OCR 텍스트는 보존)
```

- `ExtractionResult.errors`: 파이프라인 레벨 에러/경고 리스트
- 부분 결과 반환: LLM이 실패해도 OCR 텍스트와 마크다운은 항상 반환

### 10.2 배치 처리

```python
from docpick.batch import BatchProcessor

processor = BatchProcessor(concurrency=4)
result = processor.process_directory("./documents/", schema=InvoiceSchema, recursive=True)

# result.total, result.succeeded, result.failed
# result.results: dict[str, ExtractionResult]  # per-file
# result.errors: dict[str, str]                # per-file errors
```

- `asyncio.Semaphore` 기반 동시 실행 제어
- `run_in_executor`로 동기 OCR/LLM을 스레드풀에서 실행
- CLI: `docpick batch ./dir/ --schema invoice --output ./results/ --concurrency 4 --recursive`
- rich progress bar (SpinnerColumn + BarColumn + TimeElapsed)

---

## 11. 테스트 전략

### 11.1 단계별 테스트

| 단계 | 대상 | 방법 |
|------|------|------|
| Unit | 스키마, 검증, 프롬프트 생성 | pytest, OCR/LLM 모킹 |
| Integration | OCR 엔진별 정확도 | 실제 엔진 + 샘플 문서 |
| E2E | 전체 파이프라인 | 실제 문서 → JSON → 검증 |
| Benchmark | 엔진별 속도/정확도 비교 | 표준 데이터셋 |

### 11.2 테스트 문서셋

| 카테고리 | 문서 수 | 소스 |
|---------|---------|------|
| Invoice (영문) | 20+ | 공개 샘플 |
| Invoice (한국어 세금계산서) | 10+ | 직접 생성 |
| Receipt | 10+ | 공개 샘플 |
| B/L | 5+ | 공개 샘플 |
| ID (MRZ) | 5+ | 합성 생성 |

---

## 12. 경쟁 우위

| 기능 | Docpick | Docling | Marker | Unstract | Textract |
|------|-------|---------|--------|----------|----------|
| 커스텀 스키마 → JSON | **O** | Beta | 부분적 | O | X |
| 로컬 LLM | **O** | X | 선택적 | O (Ollama) | X |
| 내장 엔터프라이즈 스키마 | **O** | X | X | X | 부분적 |
| 검증 규칙 엔진 | **O** | X | X | X | X |
| 한국어 1st-class | **O** | 플러그인 | O | X | O |
| pip install 즉시 사용 | **O** | O | O | X (Docker) | X |
| Apache 2.0 | **O** | MIT | GPL | AGPL | 상용 |
| API 과금 | **$0** | $0 | $0 | $0 | ~$10/1K |
