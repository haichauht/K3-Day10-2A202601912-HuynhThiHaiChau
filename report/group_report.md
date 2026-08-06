# Báo cáo tổng hợp — Day 10: Data Pipeline & Data Observability

> Đây là báo cáo tổng hợp bắt buộc theo Checkpoint C5. Bài được thực hiện cá nhân nên “nhóm” có một thành viên; không có phần việc của người khác được khai báo.

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K3 |
| Hình thức | Cá nhân (nhóm một thành viên) |
| Repository | `K3-Day10-2A202601912-HuynhThiHaiChau` |
| GitHub | <https://github.com/haichauht/K3-Day10-2A202601912-HuynhThiHaiChau> |
| Ngày hoàn thành | 2026-08-06 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Huỳnh Thị Hải Châu | 2A202601912 | Phát triển và tích hợp toàn bộ bài | `src/`, `script/`, `data/`, `report/`, kiểm thử và dashboard |

## 2. Tóm tắt kết quả

Bài làm đã hoàn thành pipeline RAG có quan sát dữ liệu từ đầu đến cuối: lấy 24 bài báo từ Crossref, lưu raw snapshot, chuẩn hóa dữ liệu, tạo văn bản embedding, sinh vector 384 chiều bằng MiniLM, lập ba collection ChromaDB độc lập và đánh giá bằng một test set cố định gồm 16 câu hỏi. Baseline sinh đầy đủ raw, clean, embedding, answers, metrics, quality, freshness và Markdown report. Sáu kịch bản tạo lỗi có log gồm xóa năm bản ghi mới nhất, xóa tóm tắt, chèn noise, cắt tiêu đề, làm cũ ngày công bố và nhân đôi bản ghi. Tác động rõ nhất là xóa các tài liệu ground truth mới nhất, làm retrieval hit rate giảm từ `1.0` xuống `0.0`; quality chỉ còn 7/12 kiểm tra đạt và faithfulness giảm từ `1.0` xuống `0.3125`. Repair được thực hiện theo kiểu tái dựng pipeline từ raw snapshot đáng tin cậy, không sửa tay answer hoặc metrics. Sau repair, số dòng trở lại 24, quality đạt 12/12, freshness trở lại `fresh`, các core metrics trở về baseline và Ragas trở lại mức tương đương. Giới hạn chính là test set còn nhỏ, tập trung vào bốn tài liệu mới nhất và Ragas có dao động do LLM evaluator.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref REST API
    -> raw response + raw records
    -> cleaning/data contract
    -> MiniLM embeddings (384 chiều)
    -> ChromaDB: papers-baseline
    -> frozen test set (16 câu, SHA-256 cố định)
    -> RAG + LLM judge + Ragas
    -> quality/freshness reports
    -> deterministic corruption + corruption log
    -> ChromaDB: papers-corrupted -> đánh giá lại
    -> rebuild từ raw snapshot + cleaning contract
    -> ChromaDB: papers-repaired -> đánh giá lại
    -> comparison metrics + Markdown report + dashboard
```

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref API | Query, retry/backoff, parse DOI, lưu payload trước khi parse | `data/raw/` | Huỳnh Thị Hải Châu |
| Cleaning | Raw records | Chuẩn hóa markup, text, list, date; reject invalid; deduplicate | `data/clean/papers_clean.*` | Huỳnh Thị Hải Châu |
| Embedding/index | Clean dataframe | MiniLM, chuẩn hóa vector, cosine ChromaDB | `data/embeddings/`, `data/chroma/` | Huỳnh Thị Hải Châu |
| Evaluation | Index + frozen test set | Top-4 retrieval, deterministic answer, LLM judge, Ragas | `data/eval/`, `data/results/` | Huỳnh Thị Hải Châu |
| Observability | Dataframe + metrics | 12 quality checks, freshness 180 ngày, reporting | `data/quality/`, `data/reports/` | Huỳnh Thị Hải Châu |
| Corruption/repair | Baseline clean + raw snapshot | Sáu lỗi deterministic; rebuild repaired từ raw | Corrupted/repaired artifacts + log | Huỳnh Thị Hải Châu |
| Orchestration | Settings và module contracts | Chạy đúng thứ tự, khóa hash test set | `script/run_phase1.py`, `script/run_corruption_flow.py` | Huỳnh Thị Hải Châu |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `openai` |
| `LLM_MODEL` | `gpt-5.6-luna` |
| `RAGAS_LLM_MODEL` | `gpt-4.1-mini` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày |
| Random seed | Không dùng RNG; corruption và test set đều deterministic |

Không đưa `.env` hoặc giá trị API key vào báo cáo và repository.

### Cài đặt và chạy

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:RUN_RAGAS='1'
python script\run_phase1.py
python script\run_corruption_flow.py
python script\validate_artifacts.py
python -m pytest -q
```

| Lệnh | Trạng thái | Lần chạy dùng cho bài nộp | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công | 2026-08-06 | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow | Thành công | 2026-08-06 | `data/results/comparison_metrics.json`, `data/reports/corruption_report.md` |
| Artifact validator | Passed | 2026-08-06 | Ba collection 24/20/24, không có lỗi |
| Test suite | 3 passed | 2026-08-06 | `pytest` exit code 0 |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | `https://api.crossref.org/works` |
| Query | `agentic retrieval augmented generation large language model` |
| Filter | Trong 180 ngày đến 2026-08-06, có abstract |
| Sort | `published desc` |
| Thời điểm snapshot | 2026-08-06 |
| Raw/clean records | 24/24 |
| Retry/backoff | Tối đa 5 lần cho 429/5xx hoặc request error; backoff tối đa 8 giây |

### Raw và clean schema

| Trường | Kiểu | Bắt buộc | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | string | Có | DOI hoặc ID SHA-256 ổn định | Loại bản ghi nếu rỗng; deduplicate theo ID |
| `title` | string | Có | Tiêu đề bài báo | Bỏ HTML, chuẩn hóa khoảng trắng; loại nếu rỗng |
| `summary` | string | Có | Abstract | Bỏ markup; loại nếu rỗng |
| `authors` | list[string] | Không | Danh sách tác giả | Chuẩn hóa, khử trùng; fallback `Unknown author` |
| `categories` | list[string] | Không | Chủ đề Crossref | Chuẩn hóa, khử trùng; fallback `Uncategorized` |
| `published` | ISO date | Có | Ngày công bố | Parse UTC; loại nếu không hợp lệ |
| `age_days` | integer | Có | Tuổi dữ liệu tại ngày chạy | Tính từ `published`, tối thiểu 0 |
| `text_for_embedding` | string | Có | Văn bản chuẩn đưa vào MiniLM | Ghép có nhãn title, abstract, authors, categories, published |

Ở snapshot dùng để nộp, cleaning giữ 24/24 bản ghi và không loại duplicate baseline. `paper_id` ưu tiên DOI viết thường; nếu Crossref không có DOI thì dùng SHA-256 từ title, ngày và tác giả đầu tiên. `text_for_embedding` dùng cùng một contract cho cả ba trạng thái để thay đổi metric chỉ phản ánh dữ liệu, không phản ánh thay đổi biểu diễn.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 16 |
| `question_type` | `summary`, `authors`, `date`, `categories` |
| Cách tạo ground truth | Bốn tài liệu đầu của clean dataset, mỗi câu lưu đúng `paper_id` |
| Embedding | MiniLM L6 v2, vector 384 chiều, normalized |
| Vector store | ChromaDB cosine; `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval | Top-4 |
| Agent/LLM | LangChain Agent + OpenAI; tools `semantic_search_papers`, `lookup_paper` |
| LLM judge | OpenAI, 16 lượt cho mỗi trạng thái, fallback rate `0.0` |
| Ragas | `gpt-4.1-mini`, 16 samples mỗi trạng thái |
| Frozen test set | `data/eval/test_set.json` |
| SHA-256 | `af746223bd48c30b1ed0aacf938c2843c9bfd1232692d355ed28169a42b44280` |

Một file test set và cùng hash được kiểm tra trước/sau corruption flow. Nếu tạo câu hỏi khác cho từng trạng thái, chênh lệch có thể do evaluator drift; khóa test set giúp quy kết thay đổi cho dữ liệu và index.

## 7. Kết quả baseline

| Artifact | Đường dẫn | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | Payload gốc và 24 records đã parse |
| Cleaned dataset | `data/clean/papers_clean.csv`, `.json` | Có | 24 dòng |
| Embeddings/index | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Có | Manifest được nộp; ChromaDB sinh lại được và bị Git ignore |
| Evaluation set | `data/eval/test_set.json` | Có | 16 câu, frozen hash |
| Baseline answers/metrics | `data/results/baseline_*` | Có | Answers và metrics tách riêng |
| Quality/freshness | `data/quality/` | Có | 12/12, fresh |
| Baseline report | `data/reports/phase1_report.md` | Có | Sinh tự động |

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | Tất cả ground-truth ID xuất hiện trong top-4 |
| `mean_token_f1` | 1.0000 | Câu trả lời deterministic trùng ground truth |
| `judge_accuracy` | 1.0000 | LLM judge đánh đúng 16/16 |
| `mean_judge_score` | 5.0000 | Điểm trung bình tối đa |
| Ragas answer relevancy | 0.2412 | Mức liên quan câu trả lời do evaluator Ragas chấm |
| Ragas context precision | 0.9774 | Context top-4 hầu hết liên quan |
| Ragas context recall | 1.0000 | Context bao phủ đầy đủ ground truth |
| Ragas faithfulness | 1.0000 | Baseline answer bám context |

## 8. Data quality và freshness

| Nhóm check | Dimension | Kỳ vọng | Baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| `minimum_row_count` | Volume | Ít nhất 10 | Pass, 24 | `baseline_quality_report.json` |
| ID complete/unique | Completeness/uniqueness | 0 missing, 0 duplicate | Pass | Cùng file |
| Title/summary/embedding complete | Completeness | 0 missing | Pass | Cùng file |
| Summary length | Validity | Không có summary dưới 40 ký tự | Pass | Cùng file |
| Published/age valid | Validity | Không invalid/future | Pass | Cùng file |
| Noise marker | Validity | Không có marker lỗi | Pass | Cùng file |
| Freshness threshold | Freshness | 0 dòng quá 180 ngày | Pass | Cùng file |

Freshness được đo trên cleaned dataframe. Baseline có ngày mới nhất và cũ nhất đều là `2026-08-06`, 0/24 dòng stale, nên trạng thái là `fresh`.

## 9. Corruption scenarios và repair

Artifact dữ liệu lỗi bắt buộc của C4 là `data/clean/papers_corrupted.csv`; pipeline ghi file này rồi đọc lại bằng pandas trước khi dựng collection `papers-corrupted`.

| Corruption | Cách tạo | Bản ghi bị tác động | Tín hiệu/tác động thực tế | Repair |
| --- | --- | ---: | --- | --- |
| Drop latest | Xóa 20% bản ghi mới nhất | 5 | Mất các ground-truth docs; hit rate còn 0.0 | Tái dựng từ raw snapshot |
| Blank summary | Gán chuỗi rỗng | 1 | `summary_complete` fail | Cleaning lại từ raw |
| Inject noise | Chèn marker `CORRUPTED NOISE` | 1 | Noise check fail, một answer sai nặng | Cleaning lại và re-embed |
| Truncate title | Giữ 9/23 ký tự | 1 | Exact-title lookup suy giảm | Khôi phục title từ raw |
| Make stale | Đổi ngày thành 2000-01-01 | 1 | Freshness thành stale, 5% dòng quá cũ | Parse lại ngày nguồn |
| Duplicate row | Nhân đôi, giữ nguyên ID | 1 | 2 dòng nằm trong nhóm duplicate | Deduplicate bằng cleaning contract |

`data/results/corruption_log.json` lưu đủ loại lỗi, ID bị ảnh hưởng, số lượng và tham số. Repair trong bài là **pipeline recovery by reconstruction**: đọc lại raw snapshot đã lưu trước corruption, chạy lại cùng cleaning contract, tạo embedding mới và ghi vào collection repaired độc lập. Cách này không đoán giá trị từng ô và không chỉnh sửa metrics; nó chứng minh khả năng tái lập trạng thái phục vụ từ nguồn tin cậy khi derived dataset/index bị hỏng.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi khi lỗi | Mức phục hồi | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Retrieval hit rate | 1.0000 | 0.0000 | 1.0000 | -1.0000 | 100% | Mất/khôi phục ground-truth docs |
| Mean token F1 | 1.0000 | 0.7921 | 1.0000 | -0.2079 | 100% | Answer lexical trở về baseline |
| Judge accuracy | 1.0000 | 0.7500 | 1.0000 | -0.2500 | 100% | 12/16 rồi trở lại 16/16 |
| Mean judge score | 5.0000 | 4.0625 | 5.0000 | -0.9375 | 100% | Điểm core phục hồi hoàn toàn |
| Ragas answer relevancy | 0.2412 | 0.1244 | 0.2146 | -0.1168 | 77.17% | Phục hồi phần lớn; evaluator có dao động |
| Ragas context precision | 0.9774 | 0.9219 | 0.9896 | -0.0556 | Vượt baseline | Chênh lệch nhỏ do LLM evaluator |
| Ragas context recall | 1.0000 | 0.8125 | 1.0000 | -0.1875 | 100% | Bao phủ context được khôi phục |
| Ragas faithfulness | 1.0000 | 0.3125 | 0.9375 | -0.6875 | 90.91% | Gần baseline, không tuyên bố giống tuyệt đối |
| Quality checks | 12/12 pass | 7/12 pass | 12/12 pass | 5 check fail | 100% | Phát hiện đúng lỗi đã chèn |
| Freshness | Fresh | Stale | Fresh | 1/20 stale | 100% | Trở lại 0/24 stale |

Hai chuỗi nguyên nhân–bằng chứng:

1. Xóa năm tài liệu mới nhất chứa bốn ground-truth IDs → row count 24 xuống 20 và retrieval không thể tìm đúng ID → hit rate `1.0 → 0.0`, judge accuracy `1.0 → 0.75`.
2. Nạp raw snapshot và chạy lại cleaning/embedding/index → quality `7/12 → 12/12`, freshness `stale → fresh` → core metrics trở về baseline và Ragas trở về mức tương đương.

Token F1 vẫn còn 0.7921 dù hit rate bằng 0 vì các tài liệu cùng chủ đề có nhiều từ trùng nhau. Vì vậy bài không dùng riêng token F1 để kết luận retrieval đúng.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Ragas không chạy ổn định với model chính vì thư viện tự đặt temperature; một lần khác object kết quả không thể chuyển trực tiếp bằng `dict(result)`.
- **Nguyên nhân:** Model chính không chấp nhận temperature do Ragas áp đặt và `EvaluationResult` có giao diện riêng, không phải mapping Python thông thường.
- **Cách xử lý:** Tách `RAGAS_LLM_MODEL=gpt-4.1-mini`; chuyển `result.scores` qua Hugging Face Dataset/Pandas rồi tính mean cho từng metric.
- **Cách xác minh:** Chạy lại hai pipeline với `RUN_RAGAS=1`; cả ba metrics JSON có bốn giá trị Ragas hữu hạn và validator trả `status: passed`.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| 16 câu từ bốn tài liệu mới nhất | Chưa bao phủ toàn bộ 24 bài báo | Tạo test set có người rà soát, đo theo từng question type |
| Câu hỏi chứa exact title | Retrieval dễ hơn truy vấn tự nhiên | Thêm paraphrase và câu hỏi nhiều tài liệu, so sánh hit rate/MRR |
| Corruption severity cố định | Chỉ có một mức suy giảm | Chạy sweep 5/10/20/40% và vẽ degradation curve |
| Ragas dùng LLM evaluator | Có dao động giữa lần chạy | Lưu run metadata, chạy lặp và báo mean ± std |
| Repair dựa vào raw snapshot còn tốt | Không xử lý trường hợp source of truth cũng hỏng | Thêm checksum, versioning và secondary snapshot |

## 13. Checklist trước khi nộp

- [x] Thông tin repository và một thành viên chính xác.
- [x] Ownership khớp với module và artifact thực tế.
- [x] Baseline và corruption flow đã chạy thành công trên phiên bản nộp.
- [x] Ba trạng thái dùng cùng test set và cùng SHA-256.
- [x] Bảng metrics khớp `data/results/comparison_metrics.json`.
- [x] Kết luận quality/freshness khớp các JSON trong `data/quality/`.
- [x] `group_report.md` và `individual_2A202601912.md` nằm đúng thư mục `report/`.
- [x] Không có placeholder chưa điền trong báo cáo.
- [x] `.env` bị ignore và không nằm trong danh sách file chuẩn bị commit.
- [x] `data/chroma/` bị ignore; không commit database sinh lại được.
- [x] Không có API key/token trong source, report, log hay lịch sử Git hiện tại.
