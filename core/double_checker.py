from models.base_model import BaseModel

class DoubleChecker:
    def __init__(self, model: BaseModel):
        self.model = model
        
    def check(self, original_prompt: str, original_response: str) -> str:
        check_prompt = (
            f"Review the following response to the prompt '{original_prompt}'. "
            f"Is it logically sound, especially regarding code? If not, correct it briefly. "
            f"If it is, just output 'Verified'.\n\nResponse:\n{original_response}"
        )
        
        verification = self.model.generate(check_prompt)
        
        if "Verified" in verification or "verified" in verification.lower():
            return f"{original_response}\n\n[Double Check: Verified]"
        else:
            return f"{original_response}\n\n[Double Check Correction]:\n{verification}"
