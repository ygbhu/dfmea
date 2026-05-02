# Knowledge Provider Interface

日期：2026-05-01

## 1. 设计目标

本设计只定义平台与知识库 / RAG 系统的通用接入口。

平台不在第一阶段实现完整 RAG。

平台后续可以对接：

```text
Dify
FastGPT
LlamaIndex
LangChain
Haystack
自研 RAG
企业知识库
```

本设计不定义：

- 文档解析策略
- chunk 策略
- embedding 策略
- 向量库结构
- RAG 内部 pipeline
- rerank 策略

这些由具体 Knowledge Provider 实现。

## 2. Provider 类型

平台至少识别四类知识库范围：

```text
temporary
project
public
historical_fmea
```

### 2.1 temporary

临时资料库。

生命周期绑定 session。

用于本轮分析临时上传或输入的资料。

### 2.2 project

项目资料库。

生命周期绑定 project。

用于当前项目的 BOM、需求、设计文档、工艺文件、客户要求等。

### 2.3 public

公共资料库。

生命周期为 workspace、组织或平台级。

用于企业标准、通用规范、方法论说明、模板等。

### 2.4 historical_fmea

历史 FMEA 资料库。

用于历史 DFMEA、PFMEA、控制计划、历史问题和措施、相似案例。

历史 FMEA 是参考知识，不是当前项目事实。

## 3. 接口能力

Knowledge Provider Interface 建议包含：

```text
retrieve(query, scope, filters, options)
getEvidence(evidence_ref)
linkEvidence(target_ref, evidence_refs)
promoteTemporary(evidence_ref, target_scope)
getCapabilities()
```

第一阶段必须实现：

- `retrieve`
- `getEvidence`

其他接口可预留。

## 4. retrieve

用于检索知识。

输入：

```json
{
  "query": "查找相似冷却风扇失效模式",
  "scope": {
    "workspace_id": "ws_001",
    "project_id": "proj_001",
    "session_id": "sess_001"
  },
  "filters": {
    "knowledge_base_types": ["project", "historical_fmea"],
    "plugin_id": "dfmea",
    "source_type": ["requirement", "historical_analysis"]
  },
  "options": {
    "top_k": 10,
    "include_metadata": true
  }
}
```

输出：

```json
{
  "results": [
    {
      "evidence_ref": "ev_001",
      "knowledge_base_type": "historical_fmea",
      "source_type": "historical_analysis",
      "title": "历史风扇 DFMEA 案例",
      "content": "相关片段...",
      "score": 0.82,
      "metadata": {}
    }
  ]
}
```

要求：

- 检索必须受 scope 限制。
- 返回结果必须包含 `evidence_ref`。
- 返回结果必须标记 `knowledge_base_type`。
- 历史 FMEA 结果必须能被识别为参考知识。

## 5. getEvidence

用于根据 evidence_ref 获取证据详情。

输入：

```json
{
  "evidence_ref": "ev_001",
  "scope": {
    "workspace_id": "ws_001",
    "project_id": "proj_001",
    "session_id": "sess_001"
  }
}
```

输出：

```json
{
  "evidence_ref": "ev_001",
  "knowledge_base_type": "project",
  "source_type": "requirement",
  "title": "需求文档",
  "content": "证据内容...",
  "metadata": {
    "page": 3,
    "section": "2.1"
  }
}
```

## 6. linkEvidence

用于把 evidence refs 关联到平台对象。

第一阶段可以由平台内部实现，不要求外部 provider 实现。

目标对象可以是：

```text
artifact
ai_draft
patch
projection
```

关系类型：

```text
supported_by
derived_from
inspired_by_historical_reference
```

## 7. promoteTemporary

用于把临时资料提升为项目资料。

第一阶段可预留。

典型场景：

```text
用户临时上传文件
AI 使用后发现对项目长期有价值
用户确认后提升为 Project Knowledge
```

## 8. getCapabilities

Provider 应声明能力：

```json
{
  "provider_id": "external-rag",
  "supports_temporary": true,
  "supports_project": true,
  "supports_public": true,
  "supports_historical_fmea": true,
  "supports_promote": false,
  "supports_link_evidence": false,
  "supports_metadata_filter": true
}
```

平台根据能力决定是否启用对应功能。

## 9. Retrieval Policy

平台负责决定检索策略。

Provider 只负责执行检索。

默认优先级：

```text
1. temporary
2. project
3. historical_fmea
4. public
```

不同任务可以调整优先级。

例如：

- 当前项目分析：project 优先。
- 相似案例推荐：historical_fmea 优先。
- 方法论解释：public 优先。
- 用户刚上传资料分析：temporary 优先。

## 10. 边界原则

Knowledge Provider 不负责：

- 写 artifact。
- 创建 AI Draft Batch。
- 决定当前项目事实。
- 执行 User Confirm。
- 执行 export。

Knowledge Provider 只返回证据和参考资料。

AI 或 skill 基于知识生成业务结果时，必须进入：

```text
AI Draft Batch
User Confirm
Artifact / Edge
Projection
```

历史 FMEA 永远是参考知识，不是当前项目事实。

从历史 FMEA 生成当前项目内容时，必须进入正常 User Confirm 流程。

## 11. 第一阶段实现边界

第一阶段必须实现：

- Knowledge Provider Interface
- `retrieve`
- `getEvidence`
- knowledge_base_type 标识
- scope 约束

第一阶段暂不实现：

- 文档解析
- chunk 管理
- embedding 管理
- rerank
- promoteTemporary 完整流程
- linkEvidence 外部 provider 实现
- 多 provider 聚合排序

## 12. 待决问题

后续需要确认：

- 第一阶段对接哪个开源 RAG。
- evidence_ref 由平台生成还是 provider 生成。
- 多 provider 场景下 evidence_ref 如何全局唯一。
- metadata 需要的最小字段。
- 历史 FMEA 脱敏策略。
- public knowledge 的版本管理。
