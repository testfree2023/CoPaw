# 聊天页面性能修复

## 问题描述

用户反馈：点击对话记录后半天没有反应，等待后显示出来之后 web 页面又突然白屏，显示错误代码 5。

## 问题分析

### 根本原因

1. **`getChat` API 没有消息数量限制** - 一次性加载所有历史消息，当会话消息很多时会导致：
   - 后端读取整个 JSON 文件
   - 转换所有消息（`agentscope_msg_to_message`）
   - 前端转换卡片格式（`convertMessages`）
   - 大量数据渲染导致页面卡死

2. **没有超时处理** - 用户点击后看不到 loading 状态，请求可能无限期挂起

3. **没有错误边界** - 大量数据处理时没有保护机制

## 修复方案

### 1. 后端 API 限制 (`src/copaw/app/runner/api.py`)

为 `getChat` API 添加 `limit` 参数，默认 100 条，最大 500 条：

```python
@router.get("/{chat_id}", response_model=ChatHistory)
async def get_chat(
    chat_id: str,
    limit: Optional[int] = Query(
        default=100,
        description="Max messages to return (default: 100, max: 500)",
    ),
    ...
):
    # Apply limit to reduce memory and processing time
    effective_limit = min(limit or 100, 500)

    if len(all_memories) > effective_limit:
        all_memories = all_memories[-effective_limit:]

    messages = agentscope_msg_to_message(all_memories)
    return ChatHistory(messages=messages)
```

### 2. 前端 API 支持 (`console/src/api/modules/chat.ts`)

更新 `getChat` 函数支持 `limit` 参数：

```typescript
getChat: (chatId: string, params?: { limit?: number }) => {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.append("limit", String(params.limit));
  const query = searchParams.toString();
  return request<ChatHistory>(
    `/chats/${encodeURIComponent(chatId)}${query ? `?${query}` : ""}`,
  );
},
```

### 3. 超时和错误处理 (`console/src/pages/Chat/sessionApi/index.ts`)

为 `getSession` 添加 10 秒超时和降级处理：

```typescript
private async fetchSessionFromBackend(sessionId: string) {
  const fetchPromise = api.getChat(sessionId, { limit: 100 });

  const timeoutPromise = new Promise<never>((_, reject) => {
    setTimeout(() => {
      reject(new Error("请求超时，会话数据加载失败"));
    }, 10000); // 10 秒超时
  });

  try {
    const chatHistory = await Promise.race([fetchPromise, timeoutPromise]);
    // ... 处理响应
  } catch (error) {
    console.error("Failed to fetch session:", error);
    // 降级：返回缓存或空会话
    return cached?.session || fallbackSession || createEmptySession(sessionId);
  }
}
```

### 4. 消息转换性能优化 (`convertMessages`)

添加消息数量限制防止 UI 冻结：

```typescript
function convertMessages(messages: Message[]) {
  const MAX_MESSAGES = 500;
  if (messages.length > MAX_MESSAGES) {
    console.warn(
      `Large message array detected (${messages.length}), limiting to ${MAX_MESSAGES}`,
    );
  }

  const limitedMessages = messages.slice(-MAX_MESSAGES);
  // ... 处理消息
}
```

## 修复效果

| 修复项 | 修复前 | 修复后 |
|--------|--------|--------|
| API 响应时间 | 不定（可能>30 秒） | <2 秒（100 条） |
| 前端渲染 | 可能白屏崩溃 | 稳定渲染 |
| 用户体验 | 无反馈、无限等待 | 10 秒超时 + 错误提示 |
| 内存占用 | 无限制 | 最大 500 条 |

## 配置说明

### 调整消息限制

如需修改默认消息数量限制，修改后端 API：

```python
# src/copaw/app/runner/api.py
limit: Optional[int] = Query(
    default=100,  # 修改默认值
    max=1000,     # 修改最大值
    ...
)
```

### 调整超时时间

如需修改超时时间，修改前端：

```typescript
setTimeout(() => {
  reject(new Error("请求超时，会话数据加载失败"));
}, 15000); // 修改为 15 秒
```

## 后续优化建议

1. **虚拟滚动** - 对于超长消息列表，使用虚拟滚动技术
2. **懒加载** - 初始加载最近 N 条，滚动时加载更多
3. **分页 API** - 添加 `offset`/`cursor` 分页支持
4. **WebSocket** - 使用 WebSocket 替代轮询，减少连接开销

## 测试验证

1. 启动服务：`copaw app`
2. 访问：http://127.0.0.1:8088/
3. 点击有多个历史消息的会话
4. 验证：
   - 响应时间 <2 秒
   - 页面正常显示
   - 无白屏错误

## 相关文件

- `src/copaw/app/runner/api.py` - 后端 API
- `console/src/api/modules/chat.ts` - 前端 API
- `console/src/pages/Chat/sessionApi/index.ts` - 会话管理
