import json

text = '{"found": true, "value": "Switzerland"}'


fence = "`" * 3
wrapped = fence + "json\n" + text + "\n" + fence

print("WRAPPED:")
print(wrapped)

cleaned = wrapped.strip()
cleaned = cleaned.removeprefix(fence + "json")
cleaned = cleaned.removesuffix(fence)
cleaned = cleaned.strip()

print("CLEANED:")
print(cleaned)

data= json.loads(cleaned)
print("VALUE:", data["value"])
