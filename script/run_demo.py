from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from core.config import load_settings
from core.utils import read_json
from retrieval.agent import build_agent, run_agent_question_with_trace
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


STATE_LABELS = {
    "baseline": "Dữ liệu gốc",
    "corrupted": "Dữ liệu lỗi",
    "repaired": "Đã phục hồi",
}


class DemoDataStore:
    def __init__(self) -> None:
        self.settings = load_settings()
        self._indices: dict[str, LocalEmbeddingIndex] = {}
        self._agents: dict[str, Any] = {}
        self._index_lock = threading.Lock()
        self._agent_lock = threading.Lock()

    def _paths_for_state(self, state: str) -> dict[str, Path]:
        paths = self.settings.paths
        mapping = {
            "baseline": {
                "clean": paths.clean_json,
                "metrics": paths.baseline_metrics,
                "answers": paths.baseline_answers,
                "embeddings": paths.embeddings_json,
                "quality": paths.quality_dir / "baseline_quality_report.json",
                "freshness": paths.freshness_report,
            },
            "corrupted": {
                "clean": paths.corrupted_clean_json,
                "metrics": paths.corrupted_metrics,
                "answers": paths.corrupted_answers,
                "embeddings": paths.corrupted_embeddings_json,
                "quality": paths.quality_dir / "corrupted_quality_report.json",
                "freshness": paths.quality_dir / "corrupted_freshness_report.json",
            },
            "repaired": {
                "clean": paths.repaired_clean_json,
                "metrics": paths.repaired_metrics,
                "answers": paths.repaired_answers,
                "embeddings": paths.repaired_embeddings_json,
                "quality": paths.quality_dir / "repaired_quality_report.json",
                "freshness": paths.quality_dir / "repaired_freshness_report.json",
            },
        }
        if state not in mapping:
            raise ValueError(f"Trạng thái dữ liệu không hợp lệ: {state}")
        return mapping[state]

    @staticmethod
    def _required_json(path: Path) -> Any:
        if not path.exists():
            raise FileNotFoundError(f"Thiếu tệp bằng chứng bắt buộc cho demo: {path}")
        return read_json(path)

    def get_index(self, state: str) -> LocalEmbeddingIndex:
        self._paths_for_state(state)
        with self._index_lock:
            if state not in self._indices:
                embeddings_path = self._paths_for_state(state)["embeddings"]
                self._indices[state] = LocalEmbeddingIndex.load(
                    self.settings, embeddings_path=embeddings_path
                )
        return self._indices[state]

    def get_agent(self, state: str) -> Any:
        index = self.get_index(state)
        with self._agent_lock:
            if state not in self._agents:
                self._agents[state] = build_agent(self.settings, index)
        return self._agents[state]

    def _artifact_inventory(self) -> list[dict[str, Any]]:
        data_dir = self.settings.paths.project_dir / "data"
        artifacts: list[dict[str, Any]] = []
        allowed_suffixes = {".json", ".csv", ".md"}
        for path in sorted(data_dir.rglob("*")):
            if not path.is_file() or path.name == ".gitkeep" or path.suffix not in allowed_suffixes:
                continue
            artifacts.append(
                {
                    "path": path.relative_to(self.settings.paths.project_dir).as_posix(),
                    "group": path.parent.name,
                    "bytes": path.stat().st_size,
                }
            )
        return artifacts

    def overview(self) -> dict[str, Any]:
        states: dict[str, Any] = {}
        for state in STATE_LABELS:
            paths = self._paths_for_state(state)
            clean = self._required_json(paths["clean"])
            metrics = self._required_json(paths["metrics"])
            quality = self._required_json(paths["quality"])
            freshness = self._required_json(paths["freshness"])
            manifest = self._required_json(paths["embeddings"])
            states[state] = {
                "label": STATE_LABELS[state],
                "row_count": len(clean),
                "unique_papers": len({str(item.get("paper_id")) for item in clean}),
                "collection": manifest.get("collection_name"),
                "embedding_model": manifest.get("embedding_model"),
                "metrics": metrics,
                "quality": quality,
                "freshness": freshness,
            }

        raw_records = self._required_json(self.settings.paths.raw_records_json)
        test_set = self._required_json(self.settings.paths.eval_testset)
        corruption_log = self._required_json(self.settings.paths.corruption_log)
        agent_demo = self._required_json(self.settings.paths.demo_answers)
        flow = [
            {
                "id": "source",
                "label": "Crossref API",
                "eyebrow": "NGUỒN",
                "detail": "Metadata học thuật bên ngoài, có truy vết DOI và cơ chế thử lại khi nguồn gặp lỗi.",
                "value": f"{len(raw_records)} bài báo",
                "tone": "source",
                "purpose": "Thu thập dữ liệu bài báo thật để toàn bộ RAG có nguồn gốc rõ ràng và có thể kiểm chứng.",
                "input": f"Truy vấn “{self.settings.source_query}”, lọc bài có abstract trong 180 ngày gần nhất, tối đa {self.settings.max_results} kết quả.",
                "process": [
                    "Gửi yêu cầu tới Crossref REST API và sắp xếp bài mới nhất trước.",
                    "Tự thử lại tối đa 5 lần với backoff khi gặp 429 hoặc lỗi máy chủ 5xx.",
                    "Phân tích DOI, tiêu đề, abstract, tác giả, danh mục, ngày công bố và URL.",
                    "Dùng DOI làm paper_id; nếu thiếu DOI thì sinh mã ổn định từ nội dung bài.",
                ],
                "output": f"{len(raw_records)} PaperRecord có schema thống nhất, sẵn sàng lưu raw và làm sạch.",
                "evidence": [
                    "data/raw/crossref_response.json",
                    "data/raw/crossref_records.json",
                    "src/ingestion/crossref.py",
                ],
                "key_point": "Crossref là nguồn dữ liệu thật. Các lỗi xuất hiện sau đó là lỗi được tạo có kiểm soát trong thí nghiệm.",
            },
            {
                "id": "raw",
                "label": "Bản lưu dữ liệu gốc",
                "eyebrow": "TIẾP NHẬN",
                "detail": "Phản hồi API và các bản ghi đã phân tích được lưu nguyên trạng trước khi làm sạch.",
                "value": "2 tệp",
                "tone": "data",
                "purpose": "Tạo điểm khôi phục bất biến để có thể kiểm toán, chạy lại pipeline và sửa dữ liệu mà không đoán giá trị ban đầu.",
                "input": "Phản hồi JSON nguyên bản từ Crossref và danh sách PaperRecord vừa phân tích.",
                "process": [
                    "Lưu phản hồi API trước khi tiếp tục xử lý để parser có lỗi vẫn còn dữ liệu đối chiếu.",
                    "Lưu riêng danh sách record đã parse để các lần chạy sau không bắt buộc gọi lại Internet.",
                    "Không chỉnh sửa hai tệp raw trong luồng corruption; repair luôn đọc lại từ đây.",
                ],
                "output": "Hai snapshot: một bản phản hồi Crossref đầy đủ và một bản records có schema Python.",
                "evidence": [
                    "data/raw/crossref_response.json",
                    "data/raw/crossref_records.json",
                ],
                "key_point": "Raw snapshot là nguồn sự thật để phục hồi; nó không phải dữ liệu đưa trực tiếp vào embedding.",
            },
            {
                "id": "clean",
                "label": "Dữ liệu sạch",
                "eyebrow": "CHUYỂN ĐỔI",
                "detail": "Chuẩn hóa văn bản, ngày, tác giả và danh mục; tính tuổi dữ liệu và tạo văn bản embedding.",
                "value": f"{states['baseline']['row_count']} dòng",
                "tone": "data",
                "purpose": "Biến raw records không đồng nhất thành data contract ổn định mà embedding, RAG và quality checks đều dùng được.",
                "input": f"{len(raw_records)} PaperRecord từ raw snapshot.",
                "process": [
                    "Giải mã HTML, loại thẻ markup và chuẩn hóa khoảng trắng.",
                    "Loại record thiếu paper_id, title, summary hoặc có ngày công bố không hợp lệ.",
                    "Chuẩn hóa paper_id thành chữ thường, ngày về ISO và danh sách tác giả/danh mục không trùng.",
                    "Tính age_days, summary_chars và các trường authors_joined, categories_joined.",
                    "Ghép Title, Abstract, Authors, Categories và Published thành text_for_embedding.",
                    "Loại trùng theo paper_id, giữ bản đầu tiên rồi sắp xếp bài mới nhất trước.",
                ],
                "output": f"{states['baseline']['row_count']} dòng × 16 cột, lưu đồng thời CSV và JSON.",
                "evidence": [
                    "data/clean/papers_clean.csv",
                    "data/clean/papers_clean.json",
                    "src/ingestion/cleaning.py",
                ],
                "key_point": "text_for_embedding là biểu diễn chuẩn duy nhất được dùng cho cả ba trạng thái, nên phép so sánh không bị lệch schema.",
            },
            {
                "id": "embed",
                "label": "MiniLM",
                "eyebrow": "EMBEDDING",
                "detail": "all-MiniLM-L6-v2 tạo các vector ngữ nghĩa đã chuẩn hóa.",
                "value": "384 chiều",
                "tone": "model",
                "purpose": "Biến tài liệu và câu hỏi thành vector số để máy có thể so sánh độ gần về ngữ nghĩa.",
                "input": "Mỗi text_for_embedding gồm Title, Abstract, Authors, Categories, Published; khi tìm kiếm thì đầu vào là câu hỏi người dùng.",
                "process": [
                    "Nạp sentence-transformers/all-MiniLM-L6-v2 từ cache cục bộ; chỉ tải mạng nếu cache chưa có.",
                    "Tokenizer chia văn bản thành token và Transformer mã hóa ngữ cảnh của các token.",
                    "Mô hình gom biểu diễn token thành một sentence embedding gồm 384 số thực.",
                    "Chuẩn hóa L2 vector để khoảng cách cosine giữa câu hỏi và tài liệu so sánh ổn định.",
                ],
                "output": "Một vector 384 chiều cho mỗi bài báo và một vector 384 chiều cho mỗi câu hỏi.",
                "evidence": [
                    "data/embeddings/papers_embeddings.json",
                    "src/retrieval/embeddings.py",
                ],
                "key_point": "MiniLM không trả lời câu hỏi và không phải chatbot; nó chỉ chuyển ngữ nghĩa thành vector để phục vụ retrieval.",
            },
            {
                "id": "chroma",
                "label": "ChromaDB",
                "eyebrow": "LẬP CHỈ MỤC",
                "detail": "Các bộ sưu tập cosine tách biệt giúp ba trạng thái dữ liệu không ghi đè lẫn nhau.",
                "value": "3 bộ sưu tập",
                "tone": "model",
                "purpose": "Lưu vector cùng metadata và tìm nhanh các bài gần câu hỏi nhất.",
                "input": "Vector MiniLM, text_for_embedding và metadata như DOI, title, published, authors, categories, summary.",
                "process": [
                    "Tạo record_id theo dạng paper_id::index để mỗi dòng có mã lưu riêng.",
                    "Tạo collection dùng không gian cosine và thêm embeddings, documents, metadata.",
                    "Tách papers-baseline, papers-corrupted và papers-repaired để không ghi đè nhau.",
                    "Persist collection xuống data/chroma để lần chạy sau có thể load lại.",
                ],
                "output": "Ba kho vector độc lập để cùng một câu hỏi có thể chạy trên ba trạng thái dữ liệu.",
                "evidence": [
                    "data/chroma/chroma.sqlite3",
                    "data/embeddings/papers_embeddings.json",
                    "data/embeddings/papers_embeddings_corrupted.json",
                    "data/embeddings/papers_embeddings_repaired.json",
                ],
                "key_point": "ChromaDB chỉ lưu và truy xuất nguồn; nó không tự sinh câu trả lời.",
            },
            {
                "id": "rag",
                "label": "Câu trả lời RAG",
                "eyebrow": "TRUY XUẤT",
                "detail": "Tìm chính xác theo tiêu đề kết hợp ngữ cảnh top-k để tạo câu trả lời có căn cứ.",
                "value": f"top-{self.settings.top_k}",
                "tone": "rag",
                "purpose": "Trả lời câu hỏi bằng nội dung lấy từ collection đang chọn và luôn cho phép mở nguồn để kiểm chứng.",
                "input": f"Câu hỏi người dùng, collection đang chọn và top_k={self.settings.top_k}.",
                "process": [
                    "Nếu câu hỏi có tiêu đề trong dấu ngoặc kép, thử exact lookup theo title trước.",
                    "Dùng MiniLM tạo vector câu hỏi rồi ChromaDB tìm top-4 theo cosine.",
                    "Gộp kết quả exact và semantic, loại trùng rồi giữ tối đa bốn nguồn.",
                    "Playground trích câu trả lời deterministic từ nguồn đầu để so sánh công bằng; LangChain agent có thể gọi search/lookup rồi dùng OpenAI tổng hợp.",
                ],
                "output": "Câu trả lời, DOI/title của nguồn, nội dung truy xuất, similarity score và route đã dùng.",
                "evidence": [
                    "data/results/agent_demo_answers.json",
                    "data/results/baseline_answers.json",
                    "src/retrieval/qa.py",
                    "src/retrieval/agent.py",
                ],
                "key_point": "Câu trả lời nghe hợp lý chưa đủ; phải mở top-4 sources để xem ground-truth paper có thực sự được retrieve hay không.",
            },
            {
                "id": "evaluate",
                "label": "Đánh giá",
                "eyebrow": "ĐO LƯỜNG",
                "detail": "Bộ câu hỏi cố định đo tỷ lệ truy xuất đúng, token F1 và chất lượng theo OpenAI.",
                "value": f"{len(test_set)} câu hỏi",
                "tone": "rag",
                "purpose": "Đo riêng chất lượng retrieval và chất lượng câu trả lời bằng một bộ kiểm thử không đổi.",
                "input": f"{len(test_set)} câu hỏi = 4 bài × 4 loại: chủ đề, tác giả, ngày xuất bản và danh mục.",
                "process": [
                    "Chạy cùng câu hỏi, ground truth, MiniLM và top-k trên cả ba collection.",
                    "Retrieval hit kiểm tra DOI đáp án có nằm trong top-4 hay không.",
                    "Token F1 đo mức trùng từ giữa câu trả lời và đáp án chuẩn.",
                    "OpenAI judge chấm đúng/sai và điểm 1–5; fallback chỉ dùng nếu LLM không khả dụng.",
                    "So sánh SHA-256 trước/sau để bảo đảm test set không bị thay đổi trong thí nghiệm.",
                ],
                "output": "Metrics và từng câu trả lời có nguồn, hit, F1, judge score và reasoning.",
                "evidence": [
                    "data/eval/test_set.json",
                    "data/results/baseline_metrics.json",
                    "data/results/corrupted_metrics.json",
                    "data/results/repaired_metrics.json",
                ],
                "key_point": "Bộ kiểm thử cố định giúp kết luận rằng metrics thay đổi do dữ liệu, không phải do đổi câu hỏi hay mô hình.",
            },
            {
                "id": "observe",
                "label": "Giám sát",
                "eyebrow": "THEO DÕI",
                "detail": "Các kiểm tra chất lượng và độ mới phát hiện lỗi trước khi người dùng nhận câu trả lời sai.",
                "value": f"{len(states['baseline']['quality'].get('checks', []))} kiểm tra",
                "tone": "observe",
                "purpose": "Phát hiện vấn đề ở dữ liệu trước khi lỗi lan sang retrieval và câu trả lời cho người dùng.",
                "input": "DataFrame của từng trạng thái, ngày công bố, age_days, summary và text_for_embedding.",
                "process": [
                    "Chạy 12 checks thuộc volume, completeness, uniqueness, validity và freshness.",
                    "Kiểm tra thiếu DOI/title/summary, trùng DOI, tóm tắt ngắn, ngày sai, tuổi sai và marker nhiễu.",
                    "Đánh dấu stale nếu age_days vượt ngưỡng 180 ngày.",
                    "Ghi report JSON và bản validation trung lập trong thư mục quality/gx.",
                ],
                "output": "Baseline 12/12 đạt, corrupted 7/12 đạt, repaired 12/12 đạt; kèm freshness report.",
                "evidence": [
                    "data/quality/baseline_quality_report.json",
                    "data/quality/corrupted_quality_report.json",
                    "data/quality/repaired_quality_report.json",
                    "data/quality/freshness_report.json",
                ],
                "key_point": "Số 0 ghi nhận trong một check nghĩa là 0 vi phạm, không phải không có dữ liệu.",
            },
            {
                "id": "recover",
                "label": "Tạo lỗi → Phục hồi",
                "eyebrow": "PHỤC HỒI",
                "detail": "Sáu sự kiện tạo lỗi có ghi log được sửa bằng cách dựng lại từ dữ liệu gốc có truy vết.",
                "value": f"{len(corruption_log.get('events', []))} kịch bản",
                "tone": "recover",
                "purpose": "Tạo thí nghiệm có đối chứng để chứng minh dữ liệu xấu làm RAG suy giảm và raw lineage giúp phục hồi.",
                "input": "Bản clean baseline để tạo lỗi; raw snapshot bất biến để dựng lại dữ liệu repaired.",
                "process": [
                    "Tạo 6 lỗi deterministic: xóa 5 bài mới nhất, rỗng summary, chèn noise, cắt title, làm ngày cũ và nhân đôi một dòng.",
                    "Tính lại summary_chars, age_days, text_for_embedding rồi xây papers-corrupted và đánh giá lại.",
                    "Không vá corrupted: đọc lại raw snapshot và chạy đúng build_clean_dataframe để tạo repaired.",
                    "Xây papers-repaired, chạy cùng test set và so sánh 24 → 20 → 24 cùng metrics 1.0 → 0.0 → 1.0.",
                ],
                "output": "Ba bộ dữ liệu, ba collection, corruption log và comparison report chứng minh failure/recovery.",
                "evidence": [
                    "data/results/corruption_log.json",
                    "data/results/comparison_metrics.json",
                    "data/reports/corruption_report.md",
                    "data/clean/papers_corrupted.json",
                    "data/clean/papers_clean_repaired.json",
                ],
                "key_point": "Repair từ raw tránh để sót nhiễu trong file lỗi và chứng minh khả năng tái lập của cleaning contract.",
            },
        ]
        return {
            "project": {
                "title": "Ngày 10 · Luồng dữ liệu và giám sát RAG",
                "source": self.settings.source_api,
                "source_query": self.settings.source_query,
                "source_filter": self.settings.source_filter,
                "top_k": self.settings.top_k,
                "freshness_threshold_days": self.settings.freshness_threshold_days,
                "agent_backend": agent_demo.get("backend"),
            },
            "states": states,
            "flow": flow,
            "corruption": corruption_log,
            "suggestions": [
                {
                    "question": item["question"],
                    "type": item["question_type"],
                    "ground_truth_doc_ids": item["ground_truth_doc_ids"],
                }
                for item in test_set[:8]
            ],
            "artifacts": self._artifact_inventory(),
        }

    def records(self, state: str, query: str, limit: int) -> dict[str, Any]:
        clean_path = self._paths_for_state(state)["clean"]
        records = self._required_json(clean_path)
        needle = query.strip().lower()
        if needle:
            records = [
                item
                for item in records
                if needle
                in " ".join(
                    (
                        str(item.get("paper_id", "")),
                        str(item.get("title", "")),
                        str(item.get("summary", "")),
                        str(item.get("authors_joined", "")),
                    )
                ).lower()
            ]
        total = len(records)
        selected = records[: max(1, min(limit, 50))]
        return {
            "state": state,
            "total": total,
            "records": [
                {
                    "paper_id": item.get("paper_id"),
                    "title": item.get("title"),
                    "authors": item.get("authors_joined"),
                    "published": item.get("published"),
                    "age_days": item.get("age_days"),
                    "summary_chars": item.get("summary_chars"),
                    "summary": item.get("summary"),
                    "categories": item.get("categories_joined"),
                }
                for item in selected
            ],
        }

    def chat(self, state: str, question: str, top_k: int, mode: str = "controlled") -> dict[str, Any]:
        if not question.strip():
            raise ValueError("Câu hỏi không được để trống.")
        if len(question) > 600:
            raise ValueError("Câu hỏi quá dài; vui lòng dùng tối đa 600 ký tự.")
        if mode not in {"controlled", "agent"}:
            raise ValueError(f"Chế độ trả lời không hợp lệ: {mode}")
        top_k = max(1, min(top_k, 8))
        index = self.get_index(state)
        started = time.perf_counter()
        retrieval_answer = answer_question(question.strip(), settings=self.settings, index=index, top_k=top_k)
        semantic_results = index.search(question.strip(), top_k=top_k)
        result_by_id = {item.paper_id: item for item in semantic_results}
        sources = []
        for paper_id, title, content in zip(
            retrieval_answer.retrieved_doc_ids,
            retrieval_answer.retrieved_titles,
            retrieval_answer.retrieved_contexts,
            strict=False,
        ):
            semantic = result_by_id.get(paper_id)
            sources.append(
                {
                    "paper_id": paper_id,
                    "title": title,
                    "score": 1.0 if semantic is None else semantic.score,
                    "content": content[:700],
                    "published": semantic.metadata.get("published") if semantic else None,
                    "authors": semantic.metadata.get("authors_joined") if semantic else None,
                }
            )

        evidence = None
        if mode == "controlled":
            answers_path = self._paths_for_state(state)["answers"]
            for item in self._required_json(answers_path):
                if item.get("question", "").strip().lower() == question.strip().lower():
                    evidence = {
                        "retrieval_hit": item.get("retrieval_hit"),
                        "token_f1": item.get("token_f1"),
                        "judge": item.get("judge"),
                        "ground_truth": item.get("ground_truth"),
                        "ground_truth_doc_ids": item.get("ground_truth_doc_ids"),
                    }
                    break

        if mode == "agent":
            agent_result = run_agent_question_with_trace(self.get_agent(state), question.strip())
            response_answer = agent_result["answer"]
            tool_calls = agent_result["tool_calls"]
            agent_sources: list[dict[str, Any]] = []
            seen_agent_sources: set[str] = set()
            for call in tool_calls:
                args = call.get("args", {}) if isinstance(call, dict) else {}
                candidates = []
                if call.get("name") == "lookup_paper":
                    record = index.lookup(str(args.get("paper_id_or_title", "")))
                    if record:
                        candidates = [
                            {
                                "paper_id": record["paper_id"],
                                "title": record["title"],
                                "score": 1.0,
                                "content": record["content"][:700],
                                "published": record["metadata"].get("published"),
                                "authors": record["metadata"].get("authors_joined"),
                            }
                        ]
                elif call.get("name") == "semantic_search_papers":
                    requested_top_k = max(1, min(int(args.get("top_k", top_k)), 8))
                    candidates = [
                        {
                            "paper_id": item.paper_id,
                            "title": item.title,
                            "score": item.score,
                            "content": item.content[:700],
                            "published": item.metadata.get("published"),
                            "authors": item.metadata.get("authors_joined"),
                        }
                        for item in index.search(str(args.get("query", question)), top_k=requested_top_k)
                    ]
                for candidate in candidates:
                    if candidate["paper_id"] not in seen_agent_sources:
                        seen_agent_sources.add(candidate["paper_id"])
                        agent_sources.append(candidate)
            sources = agent_sources
            route = "OpenAI Agent · LangChain tự chọn công cụ"
            mode_label = "OpenAI Agent"
        else:
            response_answer = retrieval_answer.answer
            tool_calls = []
            route = "Tìm chính xác theo tiêu đề + tìm kiếm ngữ nghĩa" if "\"" in question or "'" in question else "Tìm kiếm ngữ nghĩa"
            mode_label = "So sánh ổn định"

        return {
            "state": state,
            "state_label": STATE_LABELS[state],
            "collection": index.collection_name,
            "question": question.strip(),
            "answer": response_answer,
            "mode": mode,
            "mode_label": mode_label,
            "route": route,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "sources": sources,
            "tool_calls": tool_calls,
            "evaluation_evidence": evidence,
        }


class DemoRequestHandler(SimpleHTTPRequestHandler):
    store: DemoDataStore
    static_dir: Path

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.static_dir), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[demo] {self.address_string()} · {format % args}")

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, exc: Exception, status: HTTPStatus) -> None:
        self._send_json(
            {"error": type(exc).__name__, "message": str(exc)},
            status=status,
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/health":
                self._send_json({"status": "ok"})
                return
            if parsed.path == "/api/overview":
                self._send_json(self.store.overview())
                return
            if parsed.path == "/api/records":
                params = parse_qs(parsed.query)
                state = params.get("state", ["baseline"])[0]
                query = params.get("q", [""])[0]
                limit = int(params.get("limit", ["12"])[0])
                self._send_json(self.store.records(state, query, limit))
                return
            if parsed.path == "/":
                self.path = "/index.html"
            super().do_GET()
        except (ValueError, FileNotFoundError) as exc:
            self._send_error_json(exc, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - surfaced in browser
            self._send_error_json(exc, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            self._send_json({"error": "NotFound", "message": "API endpoint không tồn tại."}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 100_000:
                raise ValueError("Kích thước nội dung yêu cầu không hợp lệ.")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            state = str(payload.get("state", "baseline"))
            question = str(payload.get("question", ""))
            top_k = int(payload.get("top_k", self.store.settings.top_k))
            mode = str(payload.get("mode", "controlled"))
            self._send_json(self.store.chat(state, question, top_k, mode))
        except (ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
            self._send_error_json(exc, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - surfaced in browser
            self._send_error_json(exc, HTTPStatus.INTERNAL_SERVER_ERROR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chạy dashboard màu hồng về giám sát RAG cho bài Day 10.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    # Windows may inherit a legacy console code page even when logs are
    # redirected. Force UTF-8 so Vietnamese startup messages cannot crash the
    # server before it begins serving requests.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    project_dir = Path(__file__).resolve().parents[1]
    DemoRequestHandler.static_dir = project_dir / "demo"
    DemoRequestHandler.store = DemoDataStore()
    server = ThreadingHTTPServer((args.host, args.port), DemoRequestHandler)
    print(f"Dashboard Day 10 đã sẵn sàng tại http://{args.host}:{args.port}")
    print("Nhấn Ctrl+C để dừng.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐang dừng máy chủ demo.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
