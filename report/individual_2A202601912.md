# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Huỳnh Thị Hải Châu |
| MSSV | 2A202601912 |
| Khóa/Lớp | K3 |
| Hình thức thực hiện | Cá nhân |
| Phạm vi chính | Toàn bộ pipeline: ingestion, cleaning, retrieval, evaluation, observability và dashboard |
| Repository | `K3_Day10_2A202601912_HuynhThiHaiChau` |
| Ngày hoàn thành | 2026-08-06 |

## 2. Phạm vi bài làm cá nhân

### Các phần đã thực hiện

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Ingestion và raw lineage | `src/ingestion/crossref.py` | Crossref REST payload | Raw response, raw records, `PaperRecord` | Hoàn thành |
| Cleaning và data contract | `src/ingestion/cleaning.py` | Raw records | Clean CSV/JSON, `text_for_embedding`, `age_days` | Hoàn thành |
| Test set và evaluation | `src/evaluation/` | Clean data, Chroma index | 16 samples, answers, metrics | Hoàn thành |
| Data observability | `src/observability/` | Ba trạng thái dataframe/metrics | Quality, freshness và Markdown reports | Hoàn thành |
| Corruption và repair | `src/ingestion/corruption.py` | Baseline clean data và raw snapshot | Corrupted/repaired data, corruption log | Hoàn thành |
| Orchestration | `src/pipelines/` | Settings và module contracts | Hai pipeline end-to-end | Hoàn thành |

### Kiểm thử và tích hợp

| Hoạt động | Phạm vi áp dụng | Kết quả |
| --- | --- | --- |
| Kiểm thử tích hợp | Toàn bộ module | 3 test component pass; compile pass |
| Cấu hình OpenAI | Agent và LLM judge | `gpt-5.6-luna`; 48/48 lượt judge dùng LLM, không fallback |
| Sửa lỗi function tools | `retrieval/agent.py` | Agent demo chạy thật 3/3 câu, không fallback |

## 3. Kết quả bài làm cá nhân

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Fetch, parse và lưu Crossref | `data/raw/` | 24 raw records có stable DOI ID | Đọc `crossref_response.json` và `crossref_records.json` |
| Làm sạch và mô hình hóa | `data/clean/papers_clean.*` | 24 rows, schema đầy đủ, ID unique | Quality baseline pass 12/12 |
| Build index và test set | `data/chroma/`, `data/embeddings/`, `data/eval/` | Ba collection riêng, test set 16 câu | Manifest và SHA-256 test set; ChromaDB local bị Git ignore và có thể dựng lại |
| Đánh giá ba trạng thái | `data/results/` | Baseline/corrupted/repaired metrics và answers | Đối chiếu ba metrics JSON |
| Báo cáo observability | `data/quality/`, `data/reports/` | Quality, freshness, comparison report | Đọc report và JSON nguồn |

Output tiêu biểu là `data/reports/corruption_report.md`, trong đó hit rate thay đổi
`1.0 → 0.0 → 1.0` và toàn bộ con số được sinh trực tiếp từ artifacts.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline phải chứng minh dữ liệu ảnh hưởng trực tiếp đến RAG, không chỉ chạy ETL. Vì vậy bài làm lưu
raw snapshot để truy vết, cố định test set, tạo corruption có log, đo lại cùng evaluator và repair từ
raw snapshot đáng tin cậy.

### Cách triển khai

- Crossref được gọi với timeout, tối đa 5 lần retry/backoff cho lỗi tạm thời và lưu raw response trước khi parse.
- DOI được dùng làm stable `paper_id`; record không có DOI nhận ID SHA-256 ổn định từ metadata.
- Cleaning chuẩn hóa markup/whitespace, ngày, authors/categories; loại record thiếu title, summary hoặc ngày hợp lệ; dedupe theo ID.
- `text_for_embedding` ghép title, abstract, authors, categories và ngày với nhãn rõ ràng.
- Test set lấy bốn document mới nhất và tạo bốn loại câu hỏi cho mỗi document: summary, authors, date, categories.
- MiniLM tạo embedding chuẩn hóa; Chroma dùng cosine và ba collection `papers-baseline`, `papers-corrupted`, `papers-repaired`.
- Corruption deterministic gồm drop latest, blank summary, noise, truncate title, stale date và duplicate.
- Repair nạp lại `crossref_records.json` rồi chạy lại cùng cleaning contract; không sửa tay answers/metrics.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref JSON với DOI, title, abstract, author, subject, published và URL |
| Output | Raw/clean/index/eval/results/quality/reports artifacts |
| Module phụ thuộc | `core.config`, `core.utils`, pandas, ChromaDB, sentence-transformers, LangChain |
| Module sử dụng output | Retrieval, evaluator, agent, observability và reporting |
| Điều kiện lỗi cần xử lý | 429/5xx, JSON sai schema, record thiếu, duplicate, ngày sai/tương lai, thiếu credential, test set đổi |

### Cách xác minh

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe script\run_phase1.py
.\.venv\Scripts\python.exe script\run_corruption_flow.py
```

- **Kết quả mong đợi:** tests pass; hai pipeline exit code 0; đầy đủ artifacts.
- **Kết quả thực tế:** 3 tests pass; baseline và corruption flow hoàn tất.
- **Artifact/log:** `data/results/comparison_metrics.json`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần so sánh chất lượng agent giữa ba trạng thái một cách công bằng.
- **Các phương án đã cân nhắc:** tạo test set mới cho mỗi trạng thái; hoặc khóa một test set và dùng lại.
- **Phương án đã chọn:** giữ nguyên file test set và kiểm tra SHA-256 trước/sau corruption flow.
- **Lý do:** tránh evaluator drift và bảo đảm delta đến từ data state, không đến từ câu hỏi/ground truth mới.
- **Bằng chứng:** SHA-256 cuối là `af746223bd48c30b1ed0aacf938c2843c9bfd1232692d355ed28169a42b44280`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** OpenAI trả HTTP 400 khi agent dùng function tools.
- **Lỗi:** function tools không hỗ trợ `reasoning_effort=low` với `gpt-5.6-luna` trên Chat Completions.
- **Nguyên nhân gốc:** evaluator có thể dùng structured output với effort `low`, nhưng agent function tools cần effort `none` trên API surface này.
- **Cách xử lý:** cho `build_llm` nhận override; evaluator giữ `low`, riêng agent dùng `reasoning_effort="none"`.
- **Cách xác minh:** tái tạo `data/results/agent_demo_answers.json`; backend là `langchain_agent`, 3 answers không rỗng và không có fallback reason.
- **Điều học được:** cùng model nhưng tool mode khác nhau có thể yêu cầu tham số khác; cần kiểm tra artifact backend thay vì chỉ nhìn script exit 0.

## 7. Hiểu biết về luồng end-to-end

1. Crossref response được lưu nguyên bản, parse thành `PaperRecord`, cleaning thành dataframe có `text_for_embedding`, sau đó MiniLM embed và nạp Chroma.
2. Mỗi câu hỏi giữ answer chuẩn và `ground_truth_doc_ids`; retrieval hit khi top-k chứa ID chuẩn, còn token-F1/LLM judge đo answer.
3. Quality kiểm tra volume, completeness, uniqueness và validity; freshness tập trung tuổi dữ liệu, ngày mới/cũ và stale rows.
4. Cùng test set giúp các delta phản ánh corruption/repair, không phản ánh câu hỏi khác nhau.
5. Repair thành công khi repaired clean/index được dựng từ raw snapshot, quality/freshness phục hồi, core metrics trở về baseline và Ragas trở lại mức tương đương.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.0000 | 1.0000 | Năm latest records bị drop bao phủ bốn ground-truth docs |
| `mean_token_f1` | 1.0000 | 0.7921 | 1.0000 | Semantic gần nhau vẫn cho overlap, nhưng summary sai rõ rệt |
| `judge_accuracy` | 1.0000 | 0.7500 | 1.0000 | 4/16 corrupted answers bị judge đánh sai |
| `mean_judge_score` | 5.0000 | 4.0625 | 5.0000 | Giảm 0.9375 điểm rồi phục hồi hoàn toàn |
| Ragas `answer_relevancy` | 0.2412 | 0.1242 | 0.2469 | Giảm khi lỗi và trở lại mức tương đương baseline |
| Ragas `context_precision` | 0.9774 | 0.8906 | 0.9774 | Nguồn lỗi làm precision giảm |
| Ragas `context_recall` | 1.0000 | 0.8750 | 1.0000 | Repair khôi phục đủ context cần thiết |
| Ragas `faithfulness` | 1.0000 | 0.3438 | 0.9688 | Faithfulness giảm mạnh rồi phục hồi gần baseline |
| Quality checks | PASS 12/12 | FAIL (7/12 passed) | PASS 12/12 | Duplicate, missing/short summary, noise và stale bị phát hiện |
| Freshness status | Fresh | Stale | Fresh | Corrupted có 1 stale row, repaired có 0 |

### Kết luận từ số liệu

1. Drop năm latest ground-truth records → retrieval hit rate `1.0 → 0.0` → token-F1 giảm còn `0.7921` và judge accuracy còn `0.75`.
2. Re-clean từ raw snapshot → quality `FAIL → PASS`, freshness `stale → fresh` → core metrics trở lại baseline; bốn Ragas metrics trở lại mức tương đương nhưng không hoàn toàn giống do LLM evaluator có dao động.

Corruption ảnh hưởng rõ nhất là drop latest records vì test set cố định tham chiếu bốn document mới nhất;
retriever không thể hit một ID đã bị xóa. Noise summary tạo case rõ nhất: câu trả lời trở thành chuỗi noise,
token-F1 bằng 0 và judge score bằng 1.

Điểm khác kỳ vọng là token-F1 vẫn khá cao (`0.7921`) dù retrieval hit bằng 0. Kiểm tra answers cho thấy
các chapter cùng chủ đề có metadata gần nhau, nên answer sai document vẫn overlap nhiều từ với ground truth.
Điều này chứng minh không nên dùng riêng token-F1 để đánh giá retrieval correctness.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw snapshot và stable ID là nền tảng để audit và repair đúng nguồn.
2. Quality/freshness signals phải liên kết với per-question answers, không chỉ là dashboard độc lập.
3. Cần phối hợp retrieval hit, lexical metric và LLM judge vì mỗi metric có blind spot khác nhau.

### Nếu có thêm thời gian

Mở rộng test set bằng câu hỏi paraphrase do người viết, thêm nhiều mức corruption severity và đo thêm
chi phí/latency. Việc này giúp kiểm tra độ tổng quát ngoài 16 câu exact-title hiện tại.

## 10. Cam kết cá nhân

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích toàn bộ luồng end-to-end và các quyết định kỹ thuật chính.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Đây là báo cáo của bài làm cá nhân và không ghi nhận phần việc của thành viên khác.

**Họ và tên:** Huỳnh Thị Hải Châu
**Ngày xác nhận:** 2026-08-06
