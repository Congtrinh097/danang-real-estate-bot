# Chuyển Đổi Hệ Thống Sang Chuyên Biệt Mua Bán BĐS & Làm Giàu Dữ Liệu Đà Nẵng

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển đổi toàn diện hệ thống AI Bất động sản Đà Nẵng sang mô hình **chuyên biệt 100% cho Mua Bán / Chuyển nhượng / Đầu tư BĐS**, không còn hỗ trợ tìm kiếm thuê nhà đất. Xóa toàn bộ dữ liệu cho thuê (`dn-rent-*`), bổ sung bộ dữ liệu phong phú (16–20 BĐS bán thực tế đa dạng phân khúc từ 1.35 tỷ đến 26 tỷ trên toàn bộ 7 quận/huyện Đà Nẵng), nạp lại Qdrant Vector DB, và cập nhật cơ chế Router Guardrails từ chối thân thiện các yêu cầu hỏi thuê.

**Architecture:**
- **Router & Guardrail Engine (`backend/agent.py`):**
  - Cập nhật schema `IntentClassification`: Nhu cầu thuê nhà được định tuyến vào `out_of_scope`.
  - Cập nhật prompt `out_of_scope_prompt` & heuristic fallback: Phản hồi thân thiện, giải thích rõ hệ thống chỉ chuyên sâu tư vấn Mua Bán / Chuyển nhượng BĐS tại Đà Nẵng, không hỗ trợ giao dịch thuê.
  - Cập nhật schema `PropertyCriteria` & ReAct property agent: Cố định `category="sale"`.
- **Dữ Liệu BĐS (`backend/data/danang_properties.json`):**
  - Xóa 3 item thuê (`dn-rent-01`, `dn-rent-02`, `dn-rent-03`).
  - Mở rộng tập dữ liệu lên ~18 BĐS bán thuộc đầy đủ 4 loại hình (`apartment`, `house`, `land`, `villa`) trải dài khắp 7 quận huyện (Hải Châu, Sơn Trà, Ngũ Hành Sơn, Thanh Khê, Cẩm Lệ, Liên Chiểu, Hòa Vang).
- **Vector DB Service (`backend/qdrant_service.py`):**
  - Thêm cơ chế làm sạch collection và re-index an toàn.
  - Sửa lỗi đường dẫn tuyệt đối cho `backend/data/danang_properties.json` để ingest ổn định bất kể vị trí chạy.
- **Frontend UI (`frontend/src/App.jsx`):**
  - Cập nhật lời chào ban đầu (`INITIAL_GREETING`), các quick chip gợi ý, placeholder ô nhập liệu để phản ánh trọng tâm mua bán & đầu tư.
- **Automated Tests:**
  - Cập nhật các test cũ có truy vấn thuê sang mua bán (`test_agent_memory.py`, `test_router_agent.py`, `test_input_guardrail.py`, `test_pii_middleware.py`).
  - Thêm test mới xác nhận: Khi người dùng hỏi thuê nhà tại Đà Nẵng, hệ thống tự động nhận diện `out_of_scope` và đưa ra lời từ chối giải thích mua bán thân thiện.

---

## User Review Required

> [!IMPORTANT]
> **Hành vi khi người dùng hỏi thuê nhà:**
> Khi người dùng gửi câu hỏi như *"Tôi muốn tìm thuê căn hộ Sơn Trà 15 triệu"*, bot sẽ phân loại vào **`out_of_scope`** và phản hồi theo mẫu:
> *"Dạ em là trợ lý chuyên sâu về Mua Bán, Chuyển nhượng và Thẩm định Đầu tư Bất động sản tại TP. Đà Nẵng. Hiện tại hệ thống bên em không hỗ trợ tìm kiếm thuê/cho thuê nhà đất ạ. Nếu anh/chị có nhu cầu tìm mua căn hộ, nhà phố, đất nền để an cư hoặc đầu tư sinh lời tại Đà Nẵng, em rất sẵn lòng hỗ trợ anh/chị ngay ạ!"*

> [!NOTE]
> **Chiến lược đầu tư "Dòng tiền cho thuê" trong Due Diligence Agent:**
> Trong tính năng Thẩm định chuyên sâu (Deep Due Diligence), mục tiêu đầu tư `"rental_cashflow"` (mua BĐS để khai thác dòng tiền cho thuê) vẫn được giữ nguyên vì đây là bài toán tài chính của người MUA nhà, không phải người đi tìm thuê nhà.

---

## Proposed Changes

```text
backend/
├── data/
│   └── danang_properties.json   # [MODIFY] Xóa 3 item rent, bổ sung 15+ item sale phong phú 7 quận Đà Nẵng
├── qdrant_service.py            # [MODIFY] Cố định category default "sale", cơ chế reindex và fix đường dẫn json
├── agent.py                     # [MODIFY] Intent router & guardrail từ chối hỏi thuê, criteria category="sale"
frontend/
└── src/
    └── App.jsx                  # [MODIFY] Cập nhật INITIAL_GREETING, quick chips & placeholders mua bán
tests/
├── test_agent_memory.py         # [MODIFY] Cập nhật truy vấn test sang tìm mua
├── test_router_agent.py         # [MODIFY] Cập nhật test sang tìm mua + thêm test từ chối hỏi thuê
├── test_input_guardrail.py      # [MODIFY] Cập nhật test in-scope sang tìm mua + thêm test out-of-scope hỏi thuê
└── test_pii_middleware.py       # [MODIFY] Cập nhật test prompt sang tìm mua
```

---

## Detailed Task Breakdown

### Task 1: Cập Nhật Dữ Liệu Bất Động Sản Bán & Re-ingest Qdrant

**Files:**
- Modify: `backend/data/danang_properties.json`
- Modify: `backend/qdrant_service.py`

**Mô tả:**
1. Xóa bỏ hoàn toàn 3 item cho thuê:
   - `dn-rent-01` (Monarchy 2PN thuê 14tr)
   - `dn-rent-02` (Studio Mỹ Khê thuê 8.5tr)
   - `dn-rent-03` (Nhà Nguyễn Văn Linh thuê 25tr)
2. Giữ lại 3 item mua bán sẵn có:
   - `dn-sale-01` (Đất nền KĐT Sinh Thái Nam Hòa Xuân, Cẩm Lệ - 3.4 tỷ)
   - `dn-sale-02` (Biệt thự Euro Village 1 Làng Châu Âu ven Sông Hàn, Sơn Trà - 26 tỷ)
   - `dn-sale-03` (Nhà phố 3 tầng kiệt ô tô Tôn Đức Thắng, Liên Chiểu - 3.1 tỷ)
3. Thêm 15 BĐS bán mới phân bố đều khắp các quận huyện Đà Nẵng:
   - **Hải Châu:**
     - `dn-sale-04`: Căn hộ The Royal Boutique Riverside Đà Nẵng (4.85 tỷ, 77m², 2PN, view sông Hàn)
     - `dn-sale-05`: Nhà phố mặt tiền kinh doanh đường Phan Châu Trinh (14.2 tỷ, 115m², 4PN)
     - `dn-sale-06`: Căn hộ sang nhượng F.Home đường Lý Thường Kiệt (2.15 tỷ, 68m², 2PN)
   - **Sơn Trà:**
     - `dn-sale-07`: Căn hộ Peninsula Da Nang view sông Hàn & cầu Thuận Phước (3.85 tỷ, 82m², 2PN)
     - `dn-sale-08`: Nhà phố 3 tầng kiệt ô tô đường Võ Văn Kiệt gần biển Mỹ Khê (6.3 tỷ, 90m², 3PN)
     - `dn-sale-09`: Đất nền phân lô đường ven biển Hoàng Sa (8.9 tỷ, 120m², đất nền)
   - **Ngũ Hành Sơn:**
     - `dn-sale-10`: Nhà liền kề KĐT Công nghệ FPT City (4.15 tỷ, 102m², 3PN)
     - `dn-sale-11`: Đất nền biệt thự Tân Trà gần bãi tắm Non Nước (5.8 tỷ, 150m², đất nền)
     - `dn-sale-12`: Căn hộ cao cấp The Ocean Suites Đà Nẵng (3.6 tỷ, 72m², 1PN)
   - **Thanh Khê:**
     - `dn-sale-13`: Nhà 3 tầng kiệt ô tô đường Huỳnh Ngọc Huệ (2.85 tỷ, 65m², 3PN)
     - `dn-sale-14`: Nhà mặt tiền kinh doanh đường Điện Biên Phủ (9.8 tỷ, 95m², 4PN)
   - **Cẩm Lệ:**
     - `dn-sale-15`: Nhà phố 3 tầng mới hoàn thiện KĐT Nam Hòa Xuân (5.2 tỷ, 125m², 4PN)
   - **Liên Chiểu:**
     - `dn-sale-16`: Căn hộ The Ori Garden Lakeside KĐT Bàu Tràm (1.45 tỷ, 58m², 2PN)
     - `dn-sale-17`: Đất thổ cư sổ đỏ kiệt ô tô đường Nguyễn Chánh (2.25 tỷ, 90m², đất nền)
   - **Hòa Vang:**
     - `dn-sale-18`: Biệt thự vườn sinh thái ven sông Cu Đê, xã Hòa Ninh (4.6 tỷ, 320m², 3PN, villa)
     - `dn-sale-19`: Đất quy hoạch trung tâm hành chính huyện Hòa Vang, xã Hòa Phong (1.75 tỷ, 130m², đất nền)
4. Trong `backend/qdrant_service.py`:
   - Chuẩn hóa đường dẫn nạp dữ liệu: Tự động trỏ đúng `backend/data/danang_properties.json` dù chạy lệnh từ thư mục gốc hay thư mục backend.
   - Thêm phương thức `recreate_and_ingest()` để xóa sạch các vector thuê cũ và nạp mới toàn bộ giỏ hàng bán.
   - Hàm `search_properties`: Mặc định `category="sale"`.

- [ ] **Step 1: Viết test kiểm tra dữ liệu dataset chỉ chứa `category == "sale"` và có tối thiểu 15 BĐS**
- [ ] **Step 2: Cập nhật `danang_properties.json` với dữ liệu mới**
- [ ] **Step 3: Cập nhật `qdrant_service.py` và chạy re-ingest vào Qdrant container**
- [ ] **Step 4: Chạy test xác nhận thành công**

---

### Task 2: Cập Nhật Router Agent, Input Guardrails & Criteria Extraction

**Files:**
- Modify: `backend/agent.py`
- Modify: `tests/test_router_agent.py`
- Modify: `tests/test_input_guardrail.py`

**Mô tả:**
1. Trong `backend/agent.py`:
   - Schema `IntentClassification`: Cập nhật mô tả:
     - `search_property`: Chỉ dành cho nhu cầu tìm kiếm, mua bán, chuyển nhượng BĐS tại Đà Nẵng.
     - `out_of_scope`: Bao gồm các câu hỏi hỏi thuê/cho thuê BĐS (do hệ thống không hỗ trợ thuê).
   - Schema `PropertyCriteria`: Đổi trường `category` thành mặc định `"sale"`.
   - Prompt `router_prompt`: Bổ sung chỉ dẫn rõ: Nhu cầu hỏi thuê phòng trọ, thuê căn hộ, thuê nhà đất được xếp vào `out_of_scope`.
   - Heuristic fallback trong `route_intent_node`: Nếu câu hỏi có từ khóa "thuê" / "cho thuê" mà không có "mua" / "bán", tự động gán intent là `out_of_scope`.
   - Prompt `out_of_scope_prompt`: Thêm quy tắc phản hồi khi người dùng hỏi thuê nhà: Lịch sự từ chối và giới thiệu hệ thống chỉ chuyên tư vấn Mua Bán, mời người dùng tham khảo các dự án mua bán hoặc đất nền/căn hộ tại Đà Nẵng.
   - `create_property_search_agent` prompt và fallback: Loại bỏ từ ngữ "hỏi thuê", chỉ tìm kiếm BĐS mua bán.
2. Cập nhật và bổ sung tests:
   - Trong `tests/test_router_agent.py`:
     - Sửa test `test_property_search_triggers_qdrant`: đổi prompt thành "Tôi muốn tìm mua căn hộ 2 phòng ngủ tại quận Sơn Trà".
     - Thêm test `test_rent_query_classified_as_out_of_scope`: prompt "Tôi muốn tìm thuê căn hộ 2 phòng ngủ tại Sơn Trà" phải được phân loại `out_of_scope`.
   - Trong `tests/test_input_guardrail.py`:
     - Sửa test `test_in_scope_property_search_still_works`: đổi prompt thành "Tôi muốn tìm mua căn hộ tại quận Sơn Trà Đà Nẵng".
     - Thêm test `test_rent_query_receives_polite_sale_only_rejection`: phản hồi từ chối phải nêu rõ hệ thống chỉ chuyên Mua Bán.

- [ ] **Step 1: Viết test failing cho việc chặn hỏi thuê và phân loại `out_of_scope`**
- [ ] **Step 2: Cập nhật `agent.py` theo đúng thiết kế**
- [ ] **Step 3: Chạy test và xác nhận PASS**

---

### Task 3: Cập Nhật Toàn Bộ Test Suite Hiện Có

**Files:**
- Modify: `tests/test_agent_memory.py`
- Modify: `tests/test_pii_middleware.py`

**Mô tả:**
- `tests/test_agent_memory.py`: Đổi prompt ở dòng 56 từ `"Tìm thuê chung cư quận Sơn Trà"` thành `"Tìm mua chung cư quận Sơn Trà"`.
- `tests/test_pii_middleware.py`: Đổi prompt ở dòng 112 từ `"Tôi muốn thuê căn hộ 2 phòng ngủ Sơn Trà, gửi qua test@example.com"` thành `"Tôi muốn mua căn hộ 2 phòng ngủ Sơn Trà, gửi qua test@example.com"`.
- Chạy toàn bộ test suite để đảm bảo không còn bất kỳ test nào dựa vào dữ liệu hoặc ý định thuê cũ.

- [ ] **Step 1: Sửa các test files liên quan**
- [ ] **Step 2: Chạy pytest toàn diện**

---

### Task 4: Cập Nhật Frontend UI (React 19)

**Files:**
- Modify: `frontend/src/App.jsx`

**Mô tả:**
1. Lời chào khởi đầu (`INITIAL_GREETING`):
   - Đổi từ: *"Anh/chị đang có nhu cầu thuê/mua nhà đất hay cần tư vấn về thủ tục pháp lý..."*
   - Thành: *"Anh/chị đang có nhu cầu tìm mua, chuyển nhượng nhà đất hay cần thẩm định dự án, tư vấn pháp lý, sổ đỏ, hợp đồng đặt cọc ạ?"*
2. Quick Chips / Prompt Buttons gợi ý:
   - Đổi chip `"🏢 Căn hộ 2PN Sơn Trà view sông Hàn"`: Prompt gửi đi từ *"Tìm thuê căn hộ 2 phòng ngủ Sơn Trà view sông Hàn dưới 15 triệu"* thành *"Tìm mua căn hộ 2 phòng ngủ Sơn Trà view biển dưới 3.5 tỷ"*.
   - Đổi chip phụ thành: *"Tìm mua đất nền KĐT Hòa Xuân có sổ đỏ"*.
3. Placeholder thanh nhập liệu:
   - Đổi thành: *"Hỏi mua bán nhà đất, thẩm định dự án, tính lãi vay, pháp lý Đà Nẵng..."*

- [ ] **Step 1: Cập nhật `frontend/src/App.jsx`**
- [ ] **Step 2: Kiểm tra build frontend bằng `npm run build`**

---

### Task 5: Kiểm Thử Toàn Trình (Verification) & Re-ingest Thực Tế

**Mô tả:**
1. Chạy script nạp lại dữ liệu vào Qdrant:
   ```bash
   python -c "import sys; sys.path.insert(0, 'backend'); from qdrant_service import qdrant_service; qdrant_service.ingest_dataset('backend/data/danang_properties.json')"
   ```
2. Chạy toàn bộ test suites:
   ```bash
   pytest tests/test_agent_memory.py tests/test_router_agent.py tests/test_input_guardrail.py tests/test_pii_middleware.py tests/test_due_diligence_agent.py tests/test_due_diligence_api.py
   ```
3. Khởi động lại backend server để nạp giỏ hàng mới vào bộ nhớ.

- [ ] **Step 1: Re-ingest Qdrant**
- [ ] **Step 2: Chạy full automated test suite**
- [ ] **Step 3: Tạo Walkthrough Artifact**
