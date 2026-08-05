"""
rag_chain.py
- 검색된 문맥 + 질문을 프롬프트에 넣어 LLM이 답변하게 하는 RAG 체인 (LangChain LCEL)
- LLM은 Upstage Solar / Hugging Face / Google Gemini / Groq(Llama, Qwen) / 로컬 Qwen(4bit)을 지원
"""

import os
import re

import torch
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint, HuggingFacePipeline
from langchain_upstage import ChatUpstage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, LogitsProcessor, LogitsProcessorList
from transformers import pipeline as hf_pipeline

# .env 파일 로드
load_dotenv()


def format_docs(docs) -> str:
    """검색된 문서 객체들에서 텍스트만 뽑아 하나의 문자열로 결합"""
    return "\n\n".join(doc.page_content for doc in docs)


PROMPT_DEFAULT = ChatPromptTemplate.from_template(
    """
당신은 KDT 훈련생들을 위한 전문적이고 친절한 행정 도우미 챗봇입니다.
아래 제공된 [문맥(Context)]만을 바탕으로 훈련생의 [질문]에 답변해 주세요.
문맥에 없는 내용은 절대 추측하거나 지어내지 말고, "제공된 규정에서는 해당 내용을 찾을 수 없습니다."라고 답변하세요.
답변은 반드시 한국어로만 작성하고, 다른 언어(중국어, 영어 등)를 절대 섞지 마세요.

[문맥]
{context}

[질문]
{question}

[답변]
"""
)

# 서비스형(실제 생성형 AI 어시스턴트) 톤 실험용 프롬프트. 근거 규칙(문맥 밖 추측 금지,
# 한국어만)은 PROMPT_DEFAULT와 동일하게 유지하고, 페르소나/말투만 바꿔서 "장문형 답변의
# 점수가 낮은 게 내용 문제인지 어투 문제인지"를 비교할 수 있게 함.
# 이모티콘/과장된 감탄사 없이, ChatGPT류 어시스턴트처럼 핵심을 먼저 간결하게 답하는 톤으로 조정.
PROMPT_SERVICE = ChatPromptTemplate.from_template(
    """
당신은 KDT 훈련생들을 돕는 AI 어시스턴트입니다. 요즘 생성형 AI 챗봇들이 답변하는 것처럼,
정확하고 간결한 문장으로 답변해 주세요.

답변 원칙:
- 아래 [문맥(Context)]에 있는 내용만 근거로 답변하세요. 문맥에 없는 내용은 절대 추측하거나
  지어내지 말고, "제공된 규정에서는 해당 내용을 찾을 수 없습니다."라고 답변하세요.
- 핵심 답변을 한두 문장으로 먼저 명확히 제시하고, 필요하면 근거 조항을 짧게 덧붙이세요.
  불필요하게 길게 늘어놓거나, 이모티콘·과도한 감탄사·장식적인 말투는 쓰지 마세요.
- 답변은 반드시 한국어로만 작성하고, 다른 언어(중국어, 일본어, 영어 등)를 절대 섞지 마세요.

[문맥]
{context}

[질문]
{question}

[답변(한국어로만 작성)]
"""
)

PROMPT_STYLES = {"default": PROMPT_DEFAULT, "service": PROMPT_SERVICE}

# Groq에서 지금 서빙 중인 모델은 계속 바뀌므로, 404/decommissioned 에러가 나면
# console.groq.com/docs/models 에서 현재 목록을 확인하고 .env의 GROQ_*_MODEL로 덮어쓰면 됨
GROQ_MODELS = {
    "groq_llama": ("GROQ_LLAMA_MODEL", "llama-3.3-70b-versatile"),
    "groq_qwen": ("GROQ_QWEN_MODEL", "qwen/qwen3.6-27b"),
}

# 로컬 LLM은 4bit 양자화로 로드해도 수 초~수십 초가 걸리므로, get_rag_chain()이
# 여러 번(서버 시작 + /ingest 재구성) 호출돼도 모델을 한 번만 로드하도록 캐싱함.
_local_chat_model_cache: dict[str, ChatHuggingFace] = {}

_HAN_CHAR_RE = re.compile(r"[一-鿿]")


class _StopOnChineseDrift(LogitsProcessor):
    """최근 생성된 구간에 한자(중국어)가 나타나면 강제로 EOS를 내보내 생성을 중단한다.
    4bit 양자화된 소형 다국어 모델이 답변 후반부에 중국어로 새는 기존 이슈(repetition_penalty만으로는
    완전히 안 막힘)를 문장 단위가 아니라 생성 자체를 끊어서 완화하기 위함.

    한자/가나 토큰 자체를 어휘에서 통째로 금지하는 방식(_BanNonKoreanTokens, 제거됨)도 시도했으나
    Qwen 어휘의 18%(약 27000개)가 한자 포함이라 그만큼을 막으면 나머지 토큰들의 확률 분포까지
    같이 틀어져서 정상적인 한국어 단어/숫자 표기까지 오타가 나는 부작용이 실측으로 확인됨.
    그래서 "새는 걸 감지해서 즉시 끊는" 이 방식으로 되돌림 - 중국어가 완전히 0글자는 아니지만
    (감지 전 1~2글자는 새어나올 수 있음) 나머지 답변의 품질은 그대로 유지된다."""

    WINDOW_CHARS = 10
    HAN_THRESHOLD = 1

    def __init__(self, tokenizer, eos_token_id: int):
        self.tokenizer = tokenizer
        self.eos_token_id = eos_token_id

    def __call__(self, input_ids, scores):
        tail_ids = input_ids[0, -40:]
        tail_text = self.tokenizer.decode(tail_ids, skip_special_tokens=True)[-self.WINDOW_CHARS :]
        if len(_HAN_CHAR_RE.findall(tail_text)) >= self.HAN_THRESHOLD:
            forced = torch.full_like(scores, float("-inf"))
            forced[:, self.eos_token_id] = 0.0
            return forced
        return scores


def _get_local_hf_chat_model() -> ChatHuggingFace:
    model_id = os.environ.get("LOCAL_LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    if model_id in _local_chat_model_cache:
        return _local_chat_model_cache[model_id]

    print(f"[RAG Chain] 로컬 LLM 로딩 중... ({model_id}, 4bit 양자화)")
    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=quant_config,
        # "auto"는 8GB급 GPU에서 여유 메모리를 보수적으로 계산해 일부 레이어를 CPU/디스크로
        # 오프로드하려다 4bit 양자화와 충돌함(ValueError). 단일 GPU에 전량 강제 배치.
        device_map={"": 0},
    )
    text_gen_pipeline = hf_pipeline(
        task="text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=512,
        do_sample=False,
        # 4bit 양자화된 소형 다국어 모델은 답변 후반부에 반복이 생기며 중국어/일본어로 새는 경우가
        # 있어 repetition_penalty로 완화하고, 그래도 새는 경우는 _StopOnChineseDrift가 생성 자체를
        # 끊는다. no_repeat_ngram_size는 뺐음 - "1,000,000원"처럼 숫자에 같은 자리(0 등)가 반복되는
        # 정상적인 경우까지 하드하게 금지시켜서 숫자가 깨지는 부작용이 실측으로 확인됨. repetition_penalty도
        # 1.15는 같은 이유로 숫자 반복을 과하게 억누르는 경향이 있어 1.05로 낮춤.
        repetition_penalty=1.05,
        return_full_text=False,
        logits_processor=LogitsProcessorList(
            [_StopOnChineseDrift(tokenizer, eos_token_id=tokenizer.eos_token_id)]
        ),
    )
    chat_model = ChatHuggingFace(llm=HuggingFacePipeline(pipeline=text_gen_pipeline))
    _local_chat_model_cache[model_id] = chat_model
    print("[RAG Chain] 로컬 LLM 로딩 완료")
    return chat_model


def get_llm(llm_key: str = "gemini"):
    """llm_key에 따라 적절한 LLM 객체를 반환.
    새 모델을 추가/제거하려면 이 함수에 분기만 넣었다 뺐다 하면 됨."""
    if llm_key == "solar":
        model = os.environ.get("UPSTAGE_MODEL", "solar-pro")
        return ChatUpstage(model=model)

    if llm_key == "hf_open":
        repo_id = os.environ.get("HF_MODEL_ID", "Qwen/Qwen2.5-7B-Instruct")
        endpoint = HuggingFaceEndpoint(
            repo_id=repo_id,
            task="text-generation",
            huggingfacehub_api_token=os.environ.get("HF_TOKEN"),
            max_new_tokens=512,
            temperature=0.01,
        )
        return ChatHuggingFace(llm=endpoint)

    if llm_key == "gemini":
        # gemini-2.5-flash-lite/gemini-2.5-flash/gemini-1.5-flash: 신규 발급 API 키에서
        # 404(더 이상 신규 사용자에게 제공 안 함) - 계정마다 사용 가능 모델이 다를 수 있으니
        # 404가 나면 .env에 GEMINI_MODEL=다른모델명 으로 바꿔보세요.
        model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
        return ChatGoogleGenerativeAI(model=model, temperature=0)

    if llm_key in GROQ_MODELS:
        # Groq는 모델이 아니라 오픈소스 모델(Llama/Qwen 등)을 빠르게 서빙해주는 인프라.
        # 모델별로 무료 쿼터가 따로 카운트됨.
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError(".env에 GROQ_API_KEY가 없습니다.")
        env_var, default_model = GROQ_MODELS[llm_key]
        model = os.environ.get(env_var, default_model)
        kwargs = {"model": model, "temperature": 0.0}
        if llm_key == "groq_qwen":
            # qwen은 reasoning 모델이라 <think>...</think> 추론 과정을 답변에 그대로
            # 섞어서 출력함 - reasoning_format="hidden"으로 최종 답변만 남김
            # (llama 등 non-reasoning 모델은 이 파라미터 자체를 거부하므로 조건부 적용)
            kwargs["reasoning_format"] = "hidden"
        return ChatGroq(**kwargs)

    if llm_key == "hf_local":
        # transformers + bitsandbytes로 GPU에 4bit 양자화 로드 (API 키/네트워크 불필요)
        return _get_local_hf_chat_model()

    raise ValueError(
        f"알 수 없는 llm_key: {llm_key} "
        f"(가능한 값: 'solar', 'hf_open', 'gemini', 'hf_local', {', '.join(repr(k) for k in GROQ_MODELS)})"
    )


def get_rag_chain(retriever, llm_key: str = "gemini", prompt_style: str = "default"):
    print(f"\n[RAG Chain] LLM 로드 중... (llm_key={llm_key}, prompt_style={prompt_style})")
    llm = get_llm(llm_key)
    prompt = PROMPT_STYLES[prompt_style]

    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    print("[RAG Chain] RAG 파이프라인 조립 완료")
    return rag_chain


if __name__ == "__main__":
    from chunker import chunk_pages
    from loader import load_pdf_directory
    from retriever import get_or_build_store, get_retriever

    try:
        print("RAG 체인(LLM) 단독 테스트를 시작합니다...")

        pages = load_pdf_directory("data/raw")
        chunks = chunk_pages(pages)

        store = get_or_build_store("faiss", "snunlp", chunks)
        retriever = get_retriever(store, search_type="similarity", k=3)

        query = "병가를 쓰려면 어떤 서류를 내야 해?"

        for llm_key in ("solar", "hf_open", "gemini", "groq_llama", "groq_qwen", "hf_local"):
            print(f"\n================== [{llm_key}] ==================")
            try:
                chain = get_rag_chain(retriever, llm_key=llm_key)
                print(f"질문: {query}")
                answer = chain.invoke(query)
                print(f"답변: {answer}")
            except Exception as e:
                print(f"[에러] {llm_key} 호출 실패: {e}")

    except Exception as e:
        print(f"에러 발생: {e}")
