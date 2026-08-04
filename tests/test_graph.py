from langchain_core.messages import AIMessage

from src.agent.graph import MAX_ITERATIONS, run_agent


def test_agent_answers_a_question_end_to_end_with_self_correction():
    result = run_agent("Which artist has the most albums?")

    assert result["iterations"] <= MAX_ITERATIONS
    final_message = result["messages"][-1]
    assert isinstance(final_message, AIMessage)
    assert not final_message.tool_calls
    assert "Iron Maiden" in final_message.content
