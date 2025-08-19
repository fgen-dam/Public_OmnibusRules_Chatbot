import streamlit as st
from snowflake.snowpark import Session
from snowflake.cortex import complete
from snow_mfa import snowflake_connect
from snowflake.core import Root 



connection_parameters = {
        'user' : st.secrets["USER"],
        'account' : st.secrets["ACCOUNT"],
        'password' : st.secrets["PASSWORD"],
        'role' : st.secrets["ROLE"],
        'warehouse' : st.secrets["WAREHOUSE"],
        'database' : st.secrets["DATEBASE"],
        'schema' : st.secrets["SCHEMA"],
        #"private_key": pkb,
        'ocsp_fail_open':False,
        }



session = Session.builder.configs(snowflake_connect()).create()
root = Root(session)

my_service = (root
            .databases["CORTEX_SEARCH_TUTORIAL_DB"]
            .schemas["PUBLIC"]
            .cortex_search_services["OMNIBUS"]
        )


def get_chat_history():
    """
    Retrieve the chat history from the session state limited to the number of messages specified
    by the user in the sidebar options.

    Returns:
        list: The list of chat messages from the session state.
    """

    start_index = max(
        0, len(st.session_state.messages) - 5
    )
    return st.session_state.messages[start_index : len(st.session_state.messages) - 1]


def make_chat_history_summary(chat_history, question):
    """
    Generate a summary of the chat history combined with the current question to extend the query
    context. Use the language model to generate this summary.

    Args:
        chat_history (str): The chat history to include in the summary.
        question (str): The current user question to extend with the chat history.

    Returns:
        str: The generated summary of the chat history and question.
    """
    prompt = f"""
        [INST]
        Based on the chat history below and the question, generate a query that extend the question
        with the chat history provided. The query should be in natural language.
        Answer with only the query. Do not add any explanation.

        <chat_history>
        {chat_history}
        </chat_history>
        <question>
        {question}
        </question>
        [/INST]
    """

    summary = complete("mistral-7b", prompt, session=session)

    return summary


def create_prompt(user_question):
    chat_history = get_chat_history()
    if chat_history != []:
        question_summary = make_chat_history_summary(chat_history, user_question)
        prompt_context = my_service.search(
            question_summary,
            columns=["CHUNK", "LANGUAGE", "RELATIVE_PATH", "FILE_URL"],
            limit=10,
        )
    else:
        prompt_context=  my_service.search(
            user_question,
            columns=["CHUNK", "LANGUAGE", "RELATIVE_PATH", "FILE_URL"],
            limit=10,
        )
    
    prompt_final = f"""
            [INST]
            You are a helpful AI chat assistant with RAG capabilities. When a user asks you a question,
            you will also be given context provided between <context> and </context> tags. Use that context
            with the user's chat history provided in the between <chat_history> and </chat_history> tags
            to provide a summary that addresses the user's question. Ensure the answer is coherent, concise,
            and directly relevant to the user's question.

            If the user asks a generic question which cannot be answered with the given context or chat_history,
            just say "I don't know the answer to that question.

            Don't saying things like "according to the provided context".

            <chat_history>
            {chat_history}
            </chat_history>
            <context>
            {prompt_context}
            </context>
            <question>
            {user_question}
            </question>
            [/INST]
            Answer:
            """
    
    return prompt_final


def generate_answer(prompt):
    answer_parts = []
    for chunk in complete("mistral-7b", prompt, session=session):
            answer_parts.append(chunk)
            final_answer = "".join(answer_parts)

    session.close()
    return final_answer
    



############################################## Creating the Streamlit App


def main():
    st.title(f":speech_balloon: Omnibus Rules Chatbot")
    st.write("This serves as a chatbot where you can ask anything about the Omnibus Rules")

    # Function to clear the chat history
    def clear_chat_history():
        st.session_state.messages = []


    #initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []


    # display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # react to user input
    if prompt := st.chat_input("What is your question?"):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role":"user", "content": prompt})

        response = generate_answer(create_prompt(prompt))

        with st.chat_message("assistant"):
            st.markdown(response)

        st.session_state.messages.append({"role":"assistant", "content": response})


    # Create a button to clear the chat
    st.sidebar.button("Clear Chat", on_click=clear_chat_history)


if __name__ == '__main__':
    main()