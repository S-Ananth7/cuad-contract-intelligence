from cuad_ai.llm import call_model

result = call_model("Say hello in four words.!")
print(result["text"])
print(result["tokens_in"], result["tokens_out"], round(result["seconds"], 2))
