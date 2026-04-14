# OpenAPI MCP 서버 구현 스펙

SCP MCP Code Agent가 연결하는 OpenAPI MCP 서버에서 노출해야 할 툴 정의입니다.

에이전트는 **2단계 스펙 조회** 방식으로 토큰 소비를 최소화합니다:
1. `get_openapi_spec_endpoints` — 엔드포인트 목록만 조회 (compact)
2. `get_openapi_spec_detail` — 선택된 operation의 상세 스펙만 조회

하위 호환을 위해 기존 `get_openapi_spec` 도 유지할 것을 권장합니다.

---

## Tool 1: `get_openapi_spec_endpoints`

### 목적

전체 OpenAPI 스펙 대신 **엔드포인트 목록만** 반환합니다.  
에이전트가 100개 엔드포인트 중 필요한 5~10개를 선택하는 데 사용하며,
전체 스펙 대비 토큰 소비를 90% 이상 줄입니다.

### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `service_name` | `string` | ✅ | 서비스명 (예: `"block-storage"`, `"virtual-server"`) |

### 출력 형식 (JSON)

```json
{
  "service": "block-storage",
  "total": 23,
  "endpoints": [
    {
      "operationId": "listVolumes",
      "method": "GET",
      "path": "/v2/volumes",
      "summary": "볼륨 목록 조회",
      "tags": ["volumes"],
      "deprecated": false
    },
    {
      "operationId": "getVolume",
      "method": "GET",
      "path": "/v2/volumes/{volumeId}",
      "summary": "볼륨 상세 조회",
      "tags": ["volumes"],
      "deprecated": false
    },
    {
      "operationId": "createVolume",
      "method": "POST",
      "path": "/v2/volumes",
      "summary": "볼륨 생성",
      "tags": ["volumes"],
      "deprecated": false
    }
  ]
}
```

### 출력 필드 설명

| 필드 | 설명 |
|---|---|
| `service` | 요청한 서비스명 |
| `total` | 전체 엔드포인트 수 |
| `endpoints[].operationId` | 고유 식별자. `get_openapi_spec_detail` 호출 시 사용 |
| `endpoints[].method` | HTTP 메서드 (GET/POST/PUT/DELETE/PATCH) |
| `endpoints[].path` | URL 경로 |
| `endpoints[].summary` | 한 줄 설명 |
| `endpoints[].tags` | 그룹 태그 목록 |
| `endpoints[].deprecated` | 사용 중단 여부 |

### 구현 참고

- 요청 파라미터 스키마, 응답 스키마, requestBody는 **포함하지 않습니다**
- `operationId`가 없는 엔드포인트는 `{METHOD}_{path_snake_case}` 규칙으로 자동 생성 권장
  - 예: `GET /volumes/{id}` → `get_volumes_id`

---

## Tool 2: `get_openapi_spec_detail`

### 목적

`get_openapi_spec_endpoints`로 선택된 **특정 operation들의 상세 스펙만** 반환합니다.  
에이전트가 실제 코드를 생성하는 데 필요한 파라미터, 요청/응답 스키마를 포함합니다.

### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `service_name` | `string` | ✅ | 서비스명 |
| `operation_ids` | `list[string]` | ✅ | 상세 조회할 operationId 목록 |

### 출력 형식 (JSON)

선택된 operation만 포함한 **표준 OpenAPI 3.x 형식** 반환:

```json
{
  "openapi": "3.0.3",
  "info": {
    "title": "Block Storage API",
    "version": "2.0.0"
  },
  "paths": {
    "/v2/volumes/{volumeId}": {
      "get": {
        "operationId": "getVolume",
        "summary": "볼륨 상세 조회",
        "parameters": [
          {
            "name": "volumeId",
            "in": "path",
            "required": true,
            "schema": { "type": "string" }
          }
        ],
        "responses": {
          "200": {
            "description": "성공",
            "content": {
              "application/json": {
                "schema": { "$ref": "#/components/schemas/Volume" }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "Volume": {
        "type": "object",
        "properties": {
          "volumeId": { "type": "string" },
          "name": { "type": "string" },
          "size": { "type": "integer" },
          "status": { "type": "string", "enum": ["available", "in-use", "error"] }
        }
      }
    }
  }
}
```

### 구현 참고

- `operation_ids`에 없는 path는 `paths`에 포함하지 않습니다
- 선택된 operation이 `$ref`로 참조하는 컴포넌트 스키마는 **반드시 `components`에 포함**해야 합니다  
  (에이전트가 타입 정보 없이는 코드를 생성할 수 없음)
- `operationId`를 찾지 못한 경우 해당 항목은 조용히 스킵하고 나머지 결과를 반환합니다
- 빈 `operation_ids`가 오면 에러 반환 권장: `{"error": "operation_ids must not be empty"}`

---

## Tool 3: `get_openapi_spec` (레거시, 하위 호환용)

### 목적

기존 단일 조회 방식. **전체 스펙을 반환**합니다.  
`get_openapi_spec_endpoints` / `get_openapi_spec_detail`이 연결되지 않은 경우 에이전트가 자동으로 이 툴로 폴백합니다.

### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `service_name` | `string` | ✅ | 서비스명 |

### 출력

표준 OpenAPI 3.x JSON (전체 스펙).

> 2단계 툴 구현 완료 후에도 폴백 경로로 유지할 것을 권장합니다.

---

## 에이전트 호출 흐름 요약

```
에이전트
  │
  ├─1─► get_openapi_spec_endpoints("block-storage")
  │       ← [{operationId, method, path, summary}, ...]  (~3k tokens)
  │
  │     요구사항 + 엔드포인트 목록 검토 → 5개 선택
  │
  ├─2─► get_openapi_spec_detail("block-storage", ["getVolume", "listVolumes", ...])
  │       ← paths + components (선택된 5개만)  (~10k tokens)
  │
  └─3─► 코드 생성
```

**전체 스펙 직접 조회 대비 토큰 절감:** 100개 스펙 기준 약 150k → 13k (약 91% 감소)

---

## 서비스명 규칙

에이전트는 사용자가 입력한 자연어 서비스명을 그대로 전달합니다.

| 사용자 입력 | 에이전트 전달값 |
|---|---|
| `"block storage"` | `"block storage"` |
| `"virtual server"` | `"virtual server"` |
| `"Block Storage"` | `"Block Storage"` |

서버 측에서 대소문자 및 공백을 정규화하여 처리하는 것을 권장합니다.
