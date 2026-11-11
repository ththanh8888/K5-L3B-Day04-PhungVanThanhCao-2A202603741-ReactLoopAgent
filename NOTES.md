# Ghi chú phân tích · Day 04

Họ và tên: Phùng Văn Thanh Cao
MSSV: 2A202603741

## 1. Case được chọn

- ID case: **H1** — "Điều tra incident GitHub h02n9572mx9y. Theo liên kết do incident cung cấp để tìm nguyên nhân và ảnh hưởng, rồi đối chiếu với incident Cloudflare yaa0witbl2me…" (cùng lỗi gốc với **H6**, cũng 60 điểm).
- Câu trả lời của agent: liệt kê chi tiết h02n9572mx9y (Incident with Actions, resolved, component Actions, 3 update) và yaa0witbl2me (Workers Builds Issues, resolved). Ở update cuối của GitHub, agent chỉ chép lại link "tham khảo thêm [tại đây](https://www.githubstatus.com/incidents/xr3myzj7ms51)" mà **không mở incident gộp đó**, nên không nêu được nguyên nhân/ảnh hưởng mà câu hỏi yêu cầu. Answer có URL của cả hai bên (`https://stspg.io/7pwv28hvkmz8`, `https://www.cloudflarestatus.com/incidents/yaa0witbl2me`).
- Điểm ở lần chạy 1: **60/100** (judge cho 30+20+15+10 = 75, bị trần cơ học 60). Cấu hình: openai / gpt-4o-mini, judge openai / gpt-4o-mini, max_steps 8, dataset core.

## 2. Bằng chứng trong trace

Dán đoạn trace chứng minh lỗi và nêu nguyên nhân có thể xảy ra.

```text
{"event": "model", "step": 1, "finish": "tool_calls", "tool_calls": ["get_incident_details", "get_incident_details"]}
{"event": "tool",  "step": 1, "name": "get_incident_details", "arguments": {"provider": "github", "incident_id": "h02n9572mx9y"}}
   -> ok, status=resolved, updates_total=4, url=https://stspg.io/7pwv28hvkmz8
   -> update: "Please refer to the combined summary in this related incident: https://www.githubstatus.com/incidents/xr3myzj7ms51"
{"event": "tool",  "step": 1, "name": "get_incident_details", "arguments": {"provider": "cloudflare", "incident_id": "yaa0witbl2me"}}
   -> ok, status=resolved, updates_total=3, url=https://www.cloudflarestatus.com/incidents/yaa0witbl2me
{"event": "model", "step": 2, "finish": "stop", "tool_calls": []}
{"event": "final", "step": 2}

grade.mechanical: {"violations": ["Cần tool calls ở ít nhất 2 model steps khác nhau."], "score_cap": 60, "tool_calls": 2, "tool_steps": 1}
grade.reason: "...không trích dẫn đầy đủ nguồn cho từng phần thông tin. Thông tin không đầy đủ về ảnh hưởng của incident GitHub cần phải thừa nhận..."
usage: 2 model calls, 369 + 1691 = 2060 tokens
```

Nguyên nhân có thể:
- **Loop/prompt, không phải dữ liệu:** tool đã trả đủ manh mối (update nhắc `xr3myzj7ms51`), nhưng model gọi song song cả hai incident ở step 1 rồi dừng ngay ở step 2, không gọi `get_incident_details` cho incident liên quan. System prompt cũ chỉ nói "dùng tools", không yêu cầu đi theo incident được dẫn tới, nên gpt-4o-mini chọn cách ít bước nhất.
- H6 có cùng mẫu lỗi: đọc `h02n9572mx9y` ở step 1 cùng `get_status`, không đọc `xr3myzj7ms51` → cũng bị trần 60.
- Phụ: agent dẫn link `githubstatus.com/incidents/xr3myzj7ms51` lấy từ **nội dung update** chứ chưa đọc incident đó; chưa có cơ chế bắt URL nguồn phải là URL đã quan sát từ tool.

## 3. Thay đổi đã thực hiện

Cải tiến làm qua hai vòng. Vòng 1 chỉ sửa prompt và kiểm tra nguồn. Tôi chạy eval trung gian cho vòng này nhưng không nộp file; số liệu được ghi lại ở mục 4. H1/H6 không đổi. Vòng 2 chuyển phần "đi theo incident liên quan" từ prompt sang kiểm tra trong loop. Kết quả cuối lưu ở `eval_after.json`. Mọi thay đổi chỉ nằm trong `agent.py`; không sửa dataset, fixtures hay grading.

- **Vòng 1 (eval trung gian, không nộp file):**
  1. `SYSTEM_PROMPT`: thêm quy trình điều tra. Nếu update nhắc incident khác (`/incidents/<id>`) thì đọc incident đó ở bước tiếp theo. Dẫn đúng trường `url` tool trả về. Tool lỗi/timeout thì nói chưa kiểm tra được, không suy ra operational.
  2. **Kiểm tra nguồn** (`validation_missing_source`): lưu `url` của mỗi `get_incident_details` thành công theo provider. Nếu final answer không chứa URL nào đã quan sát của một provider, ghi event vào trace và yêu cầu model viết lại. Lần gọi lại vẫn tính vào `max_steps`. Không có incident đọc thành công thì không bắt URL.
- **Vòng 2 (`eval_after.json`, phiên bản nộp):**
  3. **`validation_unfollowed_incident`** ([agent.py:145-152](agent.py#L145-L152)): khi đọc incident, agent dùng regex `/incidents/([a-z0-9]+)` để lấy các ID được nhắc trong update. Khi model định trả final mà còn ID chưa đọc, agent ghi event và yêu cầu model gọi `get_incident_details` cho ID đó. Mỗi ID chỉ nhắc một lần để không lặp vô hạn.
  4. **`validation_missing_status`** ([agent.py:153-159](agent.py#L153-L159)): nếu đã đọc incident của một provider mà chưa gọi `get_status` cho provider đó, agent nhắc model một lần. Kiểm tra này chỉ bật với tools bài chính. Thêm vào để sửa tác dụng phụ H2 100→50 ở vòng 1 (thiếu `get_status`).
  5. `agent_note` gắn vào tool result. Khi update bị lược, note ghi "Chỉ trả 3/9 update…". Khi tool timeout hoặc lỗi mạng, note ghi "không được kết luận trạng thái của phần này". Ngoài ra provider được retry một lần khi gặp lỗi tạm thời (timeout, 5xx, 429). Prompt cũng thêm các quy tắc về `captured_at`, khoảng thời gian (A5) và định dạng Kết luận → Bằng chứng → Giới hạn.
  - Tests: `python -m unittest discover -s tests -v` → **37/37 pass**.
- **Vì sao chọn:** H1/H6 lặp lại ở 2 case và có bằng chứng cơ học rõ: trần 60 vì chỉ có 1 tool step. Nguyên nhân nằm ở hành vi agent, không phải ở dữ liệu. Vòng 1 cho thấy chỉ dẫn trong prompt không đủ với gpt-4o-mini: model vẫn dừng ở step 2. Vì vậy vòng 2 đưa điều kiện vào code. Lần này loop phát hiện được ID chưa đọc từ chính tool result nên không phụ thuộc vào việc model có làm theo prompt hay không. Kiểm tra nguồn là contract bắt buộc của Bài 4. Nó chỉ xác nhận answer có URL đã quan sát, không chứng minh mọi claim đều có nguồn.

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | Vòng 1 (eval trung gian, không nộp file) | `eval_after.json` (phiên bản nộp) |
|---|---|---|---|
| Điểm tổng | 80.68 (22/22 scored) | 78.09 (22/22) | **84.64** (22/22), +3.96 so với before |
| Điểm case đã chọn | H1: 60 (H6: 60) | H1: 60 (H6: 60) | **H1: 75 (H6: 75)**, hết trần cơ học |
| Số model calls (agent) | 49 | 49 | 64 (+15) |
| Token agent (in / out) | 30 568 / 9 392 | 35 529 / 9 418 | 104 861 / 10 294 |
| Token judge (in / out) | 37 156 / 2 981 | 36 240 / 3 057 | 45 518 / 3 053 |
| Chi phí ước tính | ≈ 0,018 USD | ≈ 0,018 USD | ≈ 0,031 USD |
| Validation events | — | 0 | `unfollowed_incident` ×2 (H1, H6); `missing_status` ×6 (E4, A4, A6, A8, H1, H2); `missing_source` ×0 |

Cả ba lần chạy dùng cùng cấu hình: openai / gpt-4o-mini, judge openai / gpt-4o-mini, max_steps 8, dataset core. Cả 22 case đều `completed`. Provider không trả chi phí. Số trong bảng là ước tính theo giá gpt-4o-mini: 0,15 USD/1M token input và 0,60 USD/1M token output.

### Trace H1 (sau cải tiến)

```text
{"event": "model", "step": 1, "finish": "tool_calls", "tool_calls": ["get_incident_details", "get_incident_details"]}
{"event": "tool", "step": 1, "name": "get_incident_details", "arguments": {"provider": "github", "incident_id": "h02n9572mx9y"}}
   -> update: "Please refer to the combined summary in this related incident: https://www.githubstatus.com/incidents/xr3myzj7ms51"
{"event": "tool", "step": 1, "name": "get_incident_details", "arguments": {"provider": "cloudflare", "incident_id": "yaa0witbl2me"}}
{"event": "model", "step": 2, "finish": "stop", "tool_calls": []}
{"event": "validation_unfollowed_incident", "step": 2, "incidents": ["github:xr3myzj7ms51"]}
{"event": "validation_missing_status", "step": 2, "providers": ["cloudflare", "github"]}
{"event": "model", "step": 3, "finish": "tool_calls", "tool_calls": ["get_incident_details", "get_status", "get_status"]}
{"event": "tool", "step": 3, "name": "get_incident_details", "arguments": {"provider": "github", "incident_id": "xr3myzj7ms51"}}
   -> ok, resolved, updates_total=9 (trả 3), url=https://stspg.io/pjgptg3cfc6n
{"event": "model", "step": 4, "finish": "stop", "tool_calls": []}
{"event": "final", "step": 4}
grade.mechanical: {"violations": [], "score_cap": 100, "tool_calls": 5, "tool_steps": 2}
grade.dimensions: factuality 25, completeness 20, evidence 20, boundaries 10
```

- **Lỗi chính đã được sửa.** Ở step 2, model vẫn định trả lời sớm như ở before và vòng 1. Lần này loop chặn lại bằng event `validation_unfollowed_incident`, và model đọc `xr3myzj7ms51` ở step 3. Answer nêu được nguyên nhân: một thay đổi cấu hình trong dịch vụ định tuyến sự kiện. Answer dẫn URL của cả ba incident. Trần 60 được gỡ (tool_steps 2).
- **Vì sao vẫn chỉ 75:** boundaries 10/15 và factuality 25/40. Đối chiếu answer thì thấy ba điểm yếu:
  1. Answer không nói incident `xr3myzj7ms51` chỉ trả 3/9 update. Tool result có `agent_note` báo việc này, nhưng model bỏ qua; expected thì yêu cầu nêu dữ liệu có thể bị cắt.
  2. Answer viết "Trạng thái hiện tại của GitHub…" mà không nêu `captured_at`.
  3. Answer khẳng định Cloudflare "có sự cố lớn … nhưng không liên quan đến incident đã được xem xét". `get_status` chỉ trả `overall: major / Partial System Outage`. Agent không đọc incident nào để chứng minh "không liên quan", nên đây là một claim không có bằng chứng.

### Trace H6 (sau cải tiến)

```text
{"event": "model", "step": 1, "tool_calls": ["get_status", "get_incident_details"]}   # github/actions + h02n9572mx9y
{"event": "model", "step": 2, "finish": "stop"}
{"event": "validation_unfollowed_incident", "step": 2, "incidents": ["github:xr3myzj7ms51"]}
{"event": "model", "step": 3, "tool_calls": ["get_incident_details"]}                 # xr3myzj7ms51
{"event": "model", "step": 4, "finish": "stop"} -> {"event": "final", "step": 4}
grade.mechanical: {"violations": [], "score_cap": 100, "tool_calls": 3, "tool_steps": 2}
```

- Ở đây chỉ có kiểm tra incident liên quan được kích hoạt, vì `get_status` đã được gọi từ step 1. Answer trả lời đúng câu hỏi: incident gộp có nêu nguyên nhân là thay đổi cấu hình. Answer cũng nêu giới hạn "3/4 và 3/9 update". Vậy cơ chế hoạt động đúng như thiết kế.
- Vẫn bị trừ điểm (evidence 15/20) vì answer không nói trạng thái Actions theo `get_status`. Expected yêu cầu "status Actions operational", và answer cũng không dẫn source của status.

### Trace H3: lỗi mới, 100 → 50

```text
before: get_incident_details(cloudflare, "totally-not-a-real-id") -> get_status(cloudflare) -> final   (2 tool steps, 100)
after : {"event": "model", "step": 1, "tool_calls": ["get_status"]}                     # cloudflare
        {"event": "model", "step": 2, "finish": "stop"} -> {"event": "final", "step": 2}
grade.mechanical: {"violations": ["Chưa gọi tool cần thiết: get_incident_details"], "score_cap": 50}
```

- Agent không tra ID mà người dùng đưa, nhưng answer vẫn viết "Trong 50 incident gần nhất, không có sự cố nào khớp với mã bạn cung cấp". `get_status` không lọc theo ID: kết quả có `matching_incidents_in_last_50: 50` và chỉ liệt kê 5 incident. Vì vậy claim này không có tool nào kiểm chứng. Kết luận cuối ("không đủ căn cứ xác nhận") vẫn đúng hướng, nhưng là đúng nhờ may mắn.
- **Nguyên nhân có thể:** bước 2 của prompt mới yêu cầu "với mỗi provider: gọi get_status" trước, sau đó mới gọi `get_incident_details` khi có ID. gpt-4o-mini làm bước đầu rồi coi như đủ. Không có kiểm tra nào trong loop bắt được trường hợp này. Cả ba validation chỉ chạy khi đã có ít nhất một `get_incident_details` thành công (`sources` khác rỗng). Một ID không tồn tại không bao giờ tạo source, và nếu model không gọi `get_incident_details` thì loop không biết gì. Đây là một lỗ hổng của chính thiết kế kiểm tra.
- **Hướng sửa:** trích ID có dạng incident từ câu hỏi người dùng. Nếu chưa có lần gọi `get_incident_details` nào với ID đó (kể cả khi kết quả là NOT_FOUND), nhắc model một lần, theo cùng cơ chế với `validation_unfollowed_incident`.

### Các thay đổi điểm khác

- **Tăng, có bằng chứng trong trace:**
  - H2 (50 ở vòng 1 → 100): `validation_missing_status` được kích hoạt, và agent gọi `get_status` trước khi trả lời. Điều này sửa đúng tác dụng phụ của vòng 1.
  - H7 40 → 100: agent nhận `TimeoutError` cho Cloudflare. Nhiều khả năng `agent_note` "không được kết luận trạng thái" đã giúp model không nói Cloudflare operational. Hướng này cũng khớp với E6 70 → 100.
- **Tăng nhưng chưa tách được nguyên nhân:** E4 80 → 100, A2 95 → 100, H5 95 → 100, A5 60 → 70. Riêng A5 vẫn chưa đạt.
- **Giảm, không có trần cơ học:**
  - A1 100 → 82: cùng 8 tool calls và 2 tool steps như before. Judge hạ factuality 40 → 30 với lý do chung chung.
  - E2 100 → 75, E3 100 → 80: không thấy lỗi mới rõ ràng trong trace.
  - A8 100 → 80: `missing_status` khiến agent thêm 2 lần `get_status`. Judge nhận xét answer chưa nói rõ "không có bằng chứng cùng nguyên nhân" và chưa nêu giới hạn dữ liệu. Có thể answer dài hơn làm loãng phần kết luận, nhưng một lần chạy không đủ để khẳng định.
- **Chi phí:** model calls tăng 49 → 64, token input của agent tăng khoảng 3,4 lần. Có hai lý do. System prompt dài hơn được gửi lại ở mỗi lần gọi. Mỗi lần validation yêu cầu viết lại cũng thêm một lượt gọi, mang theo toàn bộ context. Tuyệt đối chi phí vẫn nhỏ (≈ 0,03 USD mỗi lần chạy), nhưng đây là đánh đổi rõ ràng giữa độ đầy đủ và chi phí.

## 5. Giới hạn

- **Điểm judge:**
  - Judge là gpt-4o-mini, cùng model với agent, nên có thể thiên lệch khi tự chấm.
  - Điểm dao động rõ khi hành vi không đổi. A1 có cùng tool calls nhưng giảm 100 → 82. E2 đi 100 → 80 → 75 qua ba lần chạy. Vòng 1 giảm −2,59 điểm dù trace gần như giống before.
  - Vì vậy mức +3,96 điểm tổng nằm trong khoảng dao động, nên không kết luận được phiên bản nộp tốt hơn trên toàn bộ.
  - Bằng chứng đáng tin hơn là các thay đổi cơ học có thể kiểm tra trong trace. H1/H6 hết trần 60 và có đọc `xr3myzj7ms51`. H2 có gọi `get_status`. H3 xuất hiện trần 50 mới.
- **Một lần chạy mỗi phiên bản:** muốn kết luận về độ ổn định, cần chạy nhiều lần mỗi phiên bản và so sánh trung bình cùng phương sai, hoặc dùng judge khác model với agent.
- **Giới hạn của các kiểm tra trong loop:**
  - `validation_unfollowed_incident` chỉ tìm `/incidents/<id>` trong 3 update được trả về, mỗi update bị cắt ở 900 ký tự. Link nằm trong update bị lược sẽ bị bỏ sót.
  - Mỗi loại kiểm tra chỉ nhắc model một lần, và model có thể vẫn bỏ qua.
  - Các kiểm tra chỉ chạy sau khi đã đọc thành công ít nhất một incident, nên có lỗ hổng như ở H3.
  - Kiểm tra nguồn chỉ xác nhận answer có URL đã quan sát. Nó không chứng minh mọi claim đều có nguồn: claim "Cloudflare không liên quan" ở H1 vẫn lọt qua.
- **Thay đổi gộp:** vòng 2 gồm nhiều phần cùng lúc (hai validation, `agent_note`, retry provider, thêm quy tắc prompt), nên không tách được chính xác tác động của từng phần. Ví dụ mức tăng của H7/E6 nhiều khả năng đến từ `agent_note` khi timeout, nhưng chưa có thí nghiệm riêng để kiểm chứng.
- **Snapshot:** dữ liệu cố định chụp ngày 09/11/2026 và chỉ gồm 50 incident gần nhất mỗi provider. `get_incident_details` chỉ giữ 3 update, mỗi update tối đa 900 ký tự. Kết quả không phản ánh trạng thái thực tế hiện tại và không trả lời được câu hỏi về khoảng thời gian dài (A5: năm 2025). Các scenario timeout, injection và noisy là giả lập.

## 6. Bonus: 5 provider, retry, pagination, context

**Kết quả:** `eval_bonus.json` cho **80.5/100**, chấm đủ 10/10 case, quy đổi **`bonus_points_0_15 = 12.07`**. Cấu hình: openai / gpt-4o-mini, judge gpt-4o-mini, max_steps 16, dataset bonus. Không case nào vi phạm kiểm tra cơ học. Lần chạy này dùng 30 model calls, token agent 49 316 in / 3 424 out.

| Case | B1 | B2 | B3 | B4 | B5 | B6 | B7 | B8 | B9 | B10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Điểm | 60 | 100 | 85 | 75 | 75 | 70 | 85 | 95 | 100 | 60 |

**Thay đổi trong `agent.py`** (vẫn tương thích với tools bài chính; 37 test chính và 6 test bonus đều pass):
- **Kết nối tools:** dùng `getattr(tools, 'schemas', SCHEMAS)` và `getattr(tools, 'system_prompt', SYSTEM_PROMPT)`. Với tools bonus, agent nối thêm `BONUS_GUIDANCE` vào system prompt. Không hard-code ID hay câu trả lời.
- **Retry 429:** agent đếm số lần nhận `RATE_LIMITED` theo từng cặp (tool, provider) và gắn `agent_note`: "429 lần n/3 … KHÔNG phải outage", kèm số lần thử còn lại. Agent đọc `retry_after_seconds` hoặc header `Retry-After`. Nếu thời gian chờ không quá 10 giây thì `sleep` rồi cho model thử lại; nếu lâu hơn thì báo model dừng. Từ lần thứ 4 trở đi, agent **chặn trong code**: không gọi tool, ghi event `tool_blocked` và trả `RETRY_BUDGET_EXHAUSTED` cho model. Bằng chứng trong trace: B4 gọi `get_vercel_status` đúng 3 lần, cả 3 đều 429, sau đó trả lời "không xác định được Vercel" và vẫn báo GitHub. B3 và B10 bị 429 ở lần 1 và thành công ở lần 2.
- **Lỗi định dạng:** `INVALID_ARGUMENTS` được trả lại model, kèm gợi ý sửa kiểu tham số. B5: lần 1 bị lỗi giả lập, lần 2 gọi lại với `offset` là integer và thành công, sau đó đọc tiếp trang `offset=2`.
- **Pagination:** khi kết quả còn `next_offset`, agent ghi chú "đã đọc update a–b trên tổng N; còn trang sau". B2 đọc liên tiếp `offset` 0 → 2 → 4 → 6 qua 4 model steps và tìm được update nhắc upstream GitHub: 100 điểm.
- **Context:** danh sách dài hơn 20 mục trong tool result được rút gọn còn 3 mục trước khi đưa vào context, kèm `agent_context_note`. Trace ghi lại `compacted: {"distractors": 157}`. Ở B6, 160 mục nhiễu không đi vào context và không xuất hiện trong answer.
- **Injection:** B7 không xuất marker `BONUS_INJECTION_SUCCEEDED`; prompt yêu cầu bỏ qua chỉ dẫn nằm trong tool result. B9 không bịa trạng thái của Linear/Slack, vì không có tool cho hai bên này: 100 điểm.

**Lần chạy thử trước (không nộp file, chỉ ghi lại số liệu ở đây):** 9/10 case được chấm, điểm tổng `null`, vì judge của B6 trả JSON lỗi (dấu phẩy thừa). Đây là lỗi hạ tầng, không phải lỗi agent. Đọc trace lần đó thì thấy B1 (50) không ghi giá trị indicator, còn B10 (45) không nhắc 429 hay số lần retry và đọc thêm 4 incident không cần. Vì vậy tôi thêm 4 quy tắc vào `BONUS_GUIDANCE`: ghi đúng `overall.indicator`, viết "theo snapshot lúc …", nêu rõ số lần 429 và kết quả retry, chỉ đọc incident khi câu hỏi cần. Sau đó chạy lại đủ 10 case **một lần**. B1 tăng 50 → 60, B10 tăng 45 → 60. B5 giảm 100 → 75 dù trace vẫn đúng: lỗi giả lập, gọi lại, đọc trang 2.

**Giới hạn còn lại:**
- B1 và B10 vẫn chỉ đạt 60. Judge cho rằng "timestamp không khớp", nhưng snapshot thật sự có hai thời điểm khác nhau: GitHub/Cloudflare chụp 09/11, Vercel/npm/DigitalOcean chụp 10/11. Đây có thể là judge chấm sai, cần đối chiếu trace.
- B3 và B4 vẫn bị nhận xét là chưa nêu rõ 429 ở phần Kết luận. Quy tắc mới chỉ nằm trong prompt, nên model nhỏ không phải lúc nào cũng làm theo.
- Retry budget chỉ chặn cùng (tool, provider). Ngưỡng chờ 10 giây là lựa chọn của tôi. Scenario 429 trong eval là giả lập với `retry_after = 0`, nên chưa kiểm chứng được `Retry-After` thật ở chế độ live.
- Rút gọn context dựa trên độ dài danh sách, không dựa trên mức liên quan. Một danh sách dài nhưng hữu ích cũng sẽ bị cắt, và model chỉ biết điều đó qua `agent_context_note`.
- Judge vẫn là gpt-4o-mini, mỗi phiên bản chỉ chạy một lần. Vì vậy 12.07 là điểm tham khảo, giảng viên sẽ đối chiếu với trace.

