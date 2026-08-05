"""
evaluate.py
- eval/questions.csv(질문/정답)를 기준으로 로컬 LLM(hf_local, Qwen2.5-7B-Instruct 4bit)의
  RAG 답변 품질을 BERTScore + LLM-as-judge로 채점한다.
- team-07-project의 evaluate.py를 이 프로젝트(bge_m3 + faiss + 하이브리드 검색 + service 프롬프트)
  구성에 맞춰 이식한 버전. 비교 실험이 아니라 hf_local 단독 성능 확인용이라 Ragas는 포함하지 않음.

실행 전 준비물:
  pip install -r model/requirements.txt
  pip install bert-score pandas
  .env 에 UPSTAGE_API_KEY 설정 (judge LLM으로 solar 고정 사용)
  data/raw/ 에 원본 PDF 6개, eval/questions.csv 존재 확인

실행 (반드시 프로젝트 루트에서, model/src가 아니라 team-17-project/ 에서):
  python model/src/evaluate.py

결과:
  eval/hf_local_check/results_questions_faiss_bge_m3_hf_local_service.csv  (문항별 답변 + 점수)
  eval/hf_local_check/summary_questions.csv, .md                          (평균 점수 요약)
"""

import json
import os
import re
import time
from typing import Dict, Optional

import pandas as pd
from bert_score import score as bertscore_score

from chunker import chunk_pages
from loader import load_pdf_directory
from rag_chain import get_llm, get_rag_chain
from retriever import get_hybrid_retriever, get_or_build_store, get_retriever

QUESTIONS_PATH = "eval/questions.csv"
RESULTS_DIR = "eval/hf_local_check"
TOP_K = 5

# judge(solar) 호출 사이 대기 - Upstage 무료 티어 429(rate limit) 방지
API_CALL_DELAY_SECONDS = 1.0

# service.py와 동일한 구성으로 고정 (여기서는 "hf_local 자체가 쓸만한가"만 확인하는 게 목적)
USE_HYBRID_RETRIEVAL = True
VECTOR_BACKEND = "faiss"
EMBED_KEY = "bge_m3"
LLM_KEY = "hf_local"
PROMPT_STYLE = "service"

DATASET_TAG = os.path.splitext(os.path.basename(QUESTIONS_PATH))[0]

# 테스트할 때 문항 수를 줄이고 싶으면 정수를 넣으세요. 전체 실행할 땐 None.
LIMIT_QUESTIONS: Optional[int] = None

# questions.csv 기준 Question ID=14가 "규정에 명시되지 않은 내용"을 묻는 환각 테스트 문항
HALLUCINATION_TEST_QID = 14
HALLUCINATION_PASS_THRESHOLD = 4

JUDGE_PROMPT = """당신은 RAG 챗봇의 답변 품질을 평가하는 채점자입니다.
아래 [질문]에 대한 [정답]과 챗봇의 [생성된 답변]을 비교해서 0~5점으로 채점하세요.

채점 순서 (반드시 이 순서로 판단하세요):

1단계 - 먼저 [정답]의 성격을 확인하세요:
  (a) [정답]이 "~규정이 없다/명시되지 않았다/해당 사항 없음" 등 **부재 자체가 정답인 경우**
  (b) [정답]이 숫자·기간·조건·절차 등 **구체적인 사실을 담고 있는 경우**

2단계 - [정답]이 (b)(구체적 사실)인데 [생성된 답변]이 "찾을 수 없습니다/확인할 수 없습니다/
  문의하세요" 등으로 답했다면, 표현이 아무리 정중하거나 그럴듯해도 **예외 없이 0점**입니다.
  "모른다고 답하는 게 정답인 경우"는 오직 (a)일 때만 해당하며, (b)에서 모른다고 하는 것은
  명백한 오답입니다. 이 구분을 헷갈리지 마세요.

3단계 - 위 경우가 아니면 아래 기준으로 채점:
- 5점: 정답의 핵심 사실(숫자/조건/절차 등)을 정확히 포함함. 답변이 장황하거나 부가 설명이
  많아도 핵심 사실이 명확히 포함되어 있으면 감점하지 마세요 (문장 유사도가 아니라 핵심
  사실의 포함 여부로 판단).
- 3~4점: 핵심 방향은 맞지만 수치/조건 일부가 다르거나, 정답의 일부만 포함해 불완전함
- 1~2점: 질문과는 관련 있으나 핵심 내용이 명백히 틀렸거나 근거 없이 추측함(할루시네이션)
- 0점: 완전히 틀렸거나 질문과 무관하거나, 2단계에 해당하는 경우

[질문]
{question}

[정답]
{ground_truth}

[생성된 답변]
{rag_answer}

아래 JSON 형식으로만 답하세요. 다른 텍스트는 출력하지 마세요.
{{"score": <0~5 정수>, "reason": "<한 문장 채점 사유>"}}
한글만 써라
"""


def parse_judge_response(raw: str) -> Dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {"score": None, "reason": f"[파싱 실패] {raw[:200]}"}
    try:
        data = json.loads(match.group(0))
        return {"score": data.get("score"), "reason": data.get("reason", "")}
    except json.JSONDecodeError:
        return {"score": None, "reason": f"[JSON 파싱 실패] {raw[:200]}"}


def judge_answer(judge_llm, question: str, ground_truth: str, rag_answer: str) -> Dict:
    prompt = JUDGE_PROMPT.format(question=question, ground_truth=ground_truth, rag_answer=rag_answer)
    for attempt in range(2):
        try:
            raw = judge_llm.invoke(prompt).content
            return parse_judge_response(raw)
        except Exception as e:
            if attempt == 0 and "429" in str(e):
                time.sleep(10)
                continue
            return {"score": None, "reason": f"[judge 호출 실패] {e}"}


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    questions_df = pd.read_csv(QUESTIONS_PATH)
    if LIMIT_QUESTIONS:
        questions_df = questions_df.head(LIMIT_QUESTIONS)
        print(f"[테스트 모드] 질문 {LIMIT_QUESTIONS}개만 실행합니다.")

    print("PDF 로딩 및 청킹 중...")
    pages = load_pdf_directory("data/raw")
    chunks = chunk_pages(pages)
    print(f"총 {len(chunks)}개 청크 준비 완료")

    print(f"\n{'=' * 60}\nhf_local(Qwen2.5-7B-Instruct, 4bit) 단독 성능 평가\n{'=' * 60}")
    store = get_or_build_store(VECTOR_BACKEND, EMBED_KEY, chunks)
    retriever = (
        get_hybrid_retriever(store, chunks, k=TOP_K) if USE_HYBRID_RETRIEVAL else get_retriever(store, k=TOP_K)
    )
    chain = get_rag_chain(retriever, llm_key=LLM_KEY, prompt_style=PROMPT_STYLE)

    # judge는 hf_local과 별개 모델(solar)로 고정 - 채점 대상 모델이 스스로를 채점하지 않도록 함
    judge_llm = get_llm("solar")

    rows = []
    for _, row in questions_df.iterrows():
        question = row["Question"]
        ground_truth = row["Ground Truth"]

        try:
            rag_answer = chain.invoke(question)
        except Exception as e:
            rag_answer = f"[RAG 호출 실패] {e}"

        judged = judge_answer(judge_llm, question, ground_truth, rag_answer)
        time.sleep(API_CALL_DELAY_SECONDS)

        rows.append(
            {
                "Question ID": row["Question ID"],
                "Question": question,
                "Ground Truth": ground_truth,
                "Reference Source": row["Reference Source"],
                "RAG 시스템 답변": rag_answer,
                "LLM 평가 점수": judged["score"],
                "LLM 평가 사유": judged["reason"],
            }
        )
        print(f"  [{row['Question ID']:>2}] judge={judged['score']}  {str(question)[:30]}...")

    result_df = pd.DataFrame(rows)

    cands = result_df["RAG 시스템 답변"].tolist()
    refs = result_df["Ground Truth"].tolist()
    _, _, f1 = bertscore_score(cands, refs, model_type="klue/bert-base", num_layers=9, verbose=False)
    result_df["BERTScore_F1"] = f1.tolist()

    out_path = os.path.join(RESULTS_DIR, f"results_{DATASET_TAG}_{VECTOR_BACKEND}_{EMBED_KEY}_{LLM_KEY}_{PROMPT_STYLE}.csv")
    result_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n저장: {out_path}")

    halluc_row = result_df[result_df["Question ID"] == HALLUCINATION_TEST_QID]
    halluc_pass = bool(
        not halluc_row.empty
        and pd.notna(halluc_row["LLM 평가 점수"].iloc[0])
        and halluc_row["LLM 평가 점수"].iloc[0] >= HALLUCINATION_PASS_THRESHOLD
    )

    summary = {
        "실험": f"{VECTOR_BACKEND}_{EMBED_KEY}_{LLM_KEY}_{PROMPT_STYLE}",
        "임베딩": EMBED_KEY,
        "벡터DB": VECTOR_BACKEND,
        "LLM": LLM_KEY,
        "프롬프트": PROMPT_STYLE,
        "평균_BERTScore_F1": result_df["BERTScore_F1"].mean(),
        "평균_LLM평가점수": result_df["LLM 평가 점수"].mean(skipna=True),
        "환각테스트_통과": halluc_pass,
    }
    summary_df = pd.DataFrame([summary])
    summary_df.to_csv(os.path.join(RESULTS_DIR, f"summary_{DATASET_TAG}.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(RESULTS_DIR, f"summary_{DATASET_TAG}.md"), "w", encoding="utf-8") as f:
        f.write("| 실험 | 임베딩 | 벡터DB | LLM | 프롬프트 | 평균 BERTScore(F1) | 평균 Judge점수 | 환각테스트 |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        halluc = "통과" if halluc_pass else "미통과"
        f.write(
            f"| {summary['실험']} | {EMBED_KEY} | {VECTOR_BACKEND} | {LLM_KEY} | {PROMPT_STYLE} "
            f"| {summary['평균_BERTScore_F1']:.4f} | {summary['평균_LLM평가점수']:.2f} | {halluc} |\n"
        )

    print("\n" + "=" * 70)
    print("hf_local 평가 결과 요약")
    print("=" * 70)
    print(f"평균 BERTScore(F1): {summary['평균_BERTScore_F1']:.4f}")
    print(f"평균 Judge 점수(0~5): {summary['평균_LLM평가점수']:.2f}")
    print(f"환각 테스트(ID {HALLUCINATION_TEST_QID}): {'통과' if halluc_pass else '미통과'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
