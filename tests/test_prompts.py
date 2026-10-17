from un_llm_analysis.prompts import run_model_prompt


def test_run_model_prompt(mocker):
    """Test model response."""
    mock_ollama_generate = mocker.patch("un_llm_analysis.prompts.ollama.generate")
    mock_ollama_generate.return_value = {"response": "Model response", "created_at": "2026-10-17"}

    result = run_model_prompt(model="llama3.2", prompt="")
    assert result["response"] == "Model response"
