from pydantic import BaseModel

class GoverningLaw(BaseModel):
    found: bool
    quotes: list[str]
    value: str | None = None
        
good = GoverningLaw(found=True, quotes=["This Agreement is governed by the laws of Pennsylvania."], value="Pennsylvania")
print(good)

good = GoverningLaw(found="banana", quotes=["This Agreement is governed by the laws of Pennsylvania."], value="Pennsylvania")
print(good)