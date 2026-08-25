# Yurisaki / OneBot 协议笔记

本文只保存正式插件依赖的长期协议事实。历史探测过程、版本验收结果和发布资产校验不在此
记录；真实环境验证方法见 [`INTEGRATION_TESTING.md`](INTEGRATION_TESTING.md)。

## 共同事件边界

- Yurisaki 回复通过 OneBot v11 private message event 到达。
- transport 严格匹配配置的 Yurisaki sender、机器人 self ID、请求发送时间和 active
  pending request。
- 响应没有可用于关联原请求的 request ID，因此无法安全地并行归属多条回复。
- 已消费的原始事件必须从 AstrBot 默认聊天流程拦截，避免自动回复循环。

## `/a info`

插件内部只生成：

```text
/a info <validated query>
```

query 为 1–120 字符的单行字符串，不允许控制字符。响应必须包含非空 text segment；可以
同时包含 image segment。parser 从 text 中识别曲目、曲目 ID、难度、物量、谱师、曲侧、
艺术家、BPM、版本、日期和曲包等字段。

成功形状至少需要曲名或曲目 ID，以及另一个已知业务字段。未知字段可以进入
`extra_fields`，原始文本保留在 `raw_text`；任意非空提示文本不能直接视为成功。

内部 `ImageReference` 可以保留有限的 file/url 元数据，但 Agent-facing payload 只报告
`image_count`，不暴露临时媒体引用。

## `/a rand`

插件内部只生成 `/a rand`，或者附加一个经过严格白名单验证的 difficulty：

- 标级：整数 `1`–`12`，以及 `8+`、`9+`、`10+`、`11+`。
- 定数：`1.0`–`7.5` 每 0.5，`8.0`–`12.0` 每 0.1。

已确认的成功响应是单个 private event，segment 顺序为 `image → text`，没有 reply。text
以“为您推荐的曲目是：”开头，随后使用与 song info 相同的业务字段。筛选结果可能把曲名
写成带 `[...]` 难度后缀，并将难度、物量和谱师收窄为单值。

已知纯文本失败响应精确映射为：

- “谱面定数应该在 [1.0, 12.0] 区间内。” → `invalid_filter`。
- “没有找到符合条件的曲目。” → `no_matching_song`。

不要用宽泛关键词推测其他错误。成功响应必须同时具有合法歌曲文本形状和 image segment。
曲绘 URL 只用于即时发送到原 Tool caller；Tool JSON 不含 URL/file，并拒绝 localhost 与
明显的私有、回环、link-local 或 unspecified IP literal。

脱敏协议样本位于 `tests/fixtures/`。`song_info_synthetic.json` 是合成结构；
`yurisaki_rand_response.json` 保留已确认的 segment 顺序和字段形状，但账号、消息 ID、
时间戳及媒体标识均已移除或替换。

## 并发、超时与迟到响应

所有 info 和 rand 请求共享一个 global single-flight transport。不要按 Tool、用户或会话
拆锁，否则没有 request ID 的响应可能串台。

请求 timeout 后进入全局 quarantine。隔离期内来自目标 Yurisaki 的消息被视为迟到响应，
会被丢弃、拦截并重新延长安静窗口；窗口安静结束后才允许发送下一请求。shutdown 或热重载
必须中断 pending/quarantine wait、注销 raw callback 并清理 consumed marker。

## 已知非目标

`/a preview` 曾被评估，但媒体再次发送会产生明显二次压缩，因此当前不支持。不要增加
ffmpeg 重编码、音频缓存、特殊语音上传、原始 QQ 消息 hack，或修改 AstrBot/NapCat Core
来恢复该方向。其他 Yurisaki 命令同样不属于当前插件范围。
