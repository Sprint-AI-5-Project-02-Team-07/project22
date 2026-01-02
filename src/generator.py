from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory

# Global storage for chat histories (In-Memory)
store = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

def format_docs(docs):
    """검색된 문서들을 포맷팅하여 컨텍스트 문자열로 변환"""
    return "\n\n".join(
        f"--- [출처: {doc.metadata['source']}] ---\n{doc.page_content}" 
        for doc in docs
    )

def create_bidmate_chain(retriever, config):
    llm = ChatOpenAI(
        model=config['model']['llm'],
        temperature=config['model']['temperature']
    )

    # 1. Contextualize Question (History + Question -> Standalone Question)
    condense_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, "
        "just reformulate it if needed and otherwise return it as is."
    )
    condense_prompt = ChatPromptTemplate.from_messages([
        ("system", condense_system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])
    
    condense_question_chain = condense_prompt | llm | StrOutputParser()

    def contextualize_question(input: dict):
        if input.get("chat_history"):
            return condense_question_chain
        else:
            return input["input"]

    # 2. Answer Generation (Context + Question -> Answer)
    qa_system_prompt = """당신은 제안요청서(RFP) 분석 전문가 '입찰메이트 AI'입니다. 
아래 [Context]에 있는 내용만을 근거로 답변하세요.
답변 시 정보의 출처(파일명)를 괄호 안에 명시하세요.
모르는 내용은 솔직히 모른다고 답하세요.

[Context]
{context}"""

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", qa_system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])
    
    # RAG Chain (No History Management yet)
    # This chain expects keys: "input" and "chat_history"
    rag_chain = (
        RunnablePassthrough.assign(
            context=contextualize_question | retriever | format_docs
        )
        | qa_prompt
        | llm
        | StrOutputParser()
    )
    
    # 3. Wrap with Message History
    # This runnable expects key: "input" and config={"configurable": {"session_id": "..."}}
    with_message_history = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )
    
    return with_message_history