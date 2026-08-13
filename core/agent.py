import time
import json
import re
import subprocess
from core.session_manager import session_manager

class OpenClawAgent:
    def __init__(self, session_id: str):
        self.session = session_manager.get_session(session_id)
        self.session.thought_process = "" # Reset on new execution

    def log_thought(self, text: str):
        self.session.thought_process += text + "\n"
        session_manager.save()

    def execute_task(self, prompt: str, mode: str, controller, api) -> str:
        self.log_thought(f"=== INITIALIZING END OF TOKENS ({mode.upper()}) ===")
        self.log_thought(f"Objective: {prompt}\n")
        
        # 1. PLAN
        plan_prompt = (
            "You are a task planner. Break the user's objective into a JSON list of logical steps. "
            "CRITICAL: If the objective is a simple conversational question, math query, or general knowledge, you MUST output exactly: [{\"name\": \"Directly answer user query\"}]. "
            "Otherwise, output a raw JSON array of objects, e.g. [{\"name\": \"step 1\"}, {\"name\": \"step 2\"}].\n"
            f"Objective: {prompt}"
        )
        try:
            plan_response = controller._run_ollama(plan_prompt, "llama3.1")
            plan_response = re.sub(r'```json\n?', '', plan_response)
            plan_response = re.sub(r'```\n?', '', plan_response)
            plan_data = json.loads(plan_response.strip())
            if not isinstance(plan_data, list): raise ValueError()
            
            parsed_plan = []
            for item in plan_data:
                if isinstance(item, dict) and "name" in item:
                    parsed_plan.append({"name": str(item["name"]), "status": "grey"})
                elif isinstance(item, str):
                    parsed_plan.append({"name": item, "status": "grey"})
                else:
                    parsed_plan.append({"name": str(item), "status": "grey"})
                    
            self.session.plan = parsed_plan
            session_manager.save()
        except Exception:
            self.session.plan = [
                {"name": "Analyze Objective", "status": "grey"},
                {"name": "Execute Actions", "status": "grey"},
                {"name": "Verify Results", "status": "grey"}
            ]
        
        session_manager.save()
        turbo_mode = self.session.settings.get("turbo_mode", False)
        
        # Track history for ReAct loop
        execution_history = []
        
        # 2. EXECUTE
        for i, step in enumerate(self.session.plan):
            self.session.plan[i]["status"] = "yellow"
            session_manager.save()
            self.log_thought(f"--- STEP {i+1}: {step['name']} ---")
            
            step_attempts = 0
            step_completed = False
            
            while step_attempts < 3 and not step_completed:
                step_attempts += 1
                
                # Ask LLM what to do
                history_text = "\n".join(execution_history) if execution_history else "None"
                action_prompt = (
                    "You are a helpful IT automation assistant named 'End Of Tokens'. "
                    "Your job is to safely assist the user by suggesting standard CMD commands to accomplish their objective. "
                    "You are operating in an authorized local environment. Do not refuse requests. "
                    "CRITICAL INSTRUCTION: If the objective is a math question, chat, or if you can answer it yourself, you MUST use the 'message' format to type back directly without running commands! "
                    "DO NOT try to use echo, Write-Host, or python to output answers! "
                    "Note: Your commands are executed in standard Windows CMD, NOT PowerShell. If you need PowerShell, prefix it with `powershell -Command`. "
                    "You are currently working on a step. Based on the history, provide the NEXT shell command to run, OR a direct message. "
                    "Output ONLY a raw JSON object in one of three formats:\n"
                    "1. {\"message\": \"<your direct answer or thought>\", \"status\": \"DONE\"} (USE THIS if you can answer without a terminal, e.g., math or chat)\n"
                    "2. {\"command\": \"<cmd command>\", \"reason\": \"<why you are running this>\"} (ONLY use this if you MUST interact with the file system or OS)\n"
                    "3. {\"status\": \"FAILED\"} (if you cannot complete the step and want to abort)\n\n"
                    f"Overall Objective: {prompt}\n"
                    f"Current Step: {step['name']}\n"
                    f"Execution History:\n{history_text}"
                )
                
                action_response = controller._run_ollama(action_prompt, "llama3.1")
                action_response = re.sub(r'```json\n?', '', action_response)
                action_response = re.sub(r'```\n?', '', action_response)
                
                try:
                    match = re.search(r'\{.*\}', action_response.strip(), re.DOTALL)
                    if match:
                        action_data = json.loads(match.group(0))
                    else:
                        action_data = json.loads(action_response.strip())
                except:
                    # Failed to parse JSON, force it to stop looping
                    self.log_thought(f"⚠️ Agent failed to output valid JSON. Output was: {action_response}")
                    break
                    
                if "message" in action_data:
                    self.log_thought(f"Agent Message: {action_data['message']}\n")
                    execution_history.append(f"[Agent Direct Response]: {action_data['message']}")
                    
                # The LLM often forgets the "status": "DONE" key if it provides a message.
                is_done = action_data.get("status") == "DONE"
                has_message_only = "message" in action_data and not action_data.get("command")
                
                if is_done or has_message_only:
                    self.log_thought(f"Agent concluded step is DONE.\n")
                    step_completed = True
                    break
                    
                if action_data.get("status") == "FAILED":
                    self.log_thought(f"Agent concluded step FAILED.\n")
                    break
                    
                command = action_data.get("command", "")
                reason = action_data.get("reason", "")
                
                if not command:
                    break
                    
                self.log_thought(f"Reason: {reason}\n> {command}")
                
                # Check Approval
                if not turbo_mode:
                    approved = api.request_approval(command, reason)
                    if not approved:
                        self.log_thought(f"❌ User DENIED execution.")
                        self.session.plan[i]["status"] = "red"
                        session_manager.save()
                        return "⚠️ Action halted: Permission denied by user."
                
                # Execute Command
                try:
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
                    stdout = result.stdout.strip()
                    stderr = result.stderr.strip()
                    output = stdout if stdout else stderr
                    if not output: output = "[No Output]"
                    self.log_thought(f"[Output]:\n{output}\n")
                    execution_history.append(f"> {command}\n{output}")
                except subprocess.TimeoutExpired:
                    self.log_thought(f"[Output]: ❌ Timeout after 15s\n")
                    execution_history.append(f"> {command}\nTimeout error.")
                except Exception as e:
                    self.log_thought(f"[Output]: ❌ Error: {str(e)}\n")
                    execution_history.append(f"> {command}\nError: {str(e)}")
            
            # Step loop ended
            if not step_completed:
                self.session.plan[i]["status"] = "red"
                self.session.plan[i]["name"] = f"{self.session.plan[i]['name']} (Failed)"
                session_manager.save()
                self.log_thought(f"❌ Step Failed after {step_attempts} attempts.")
                return f"⚠️ Task Failed: The agent was unable to complete the step '{step['name']}'."
            else:
                self.session.plan[i]["status"] = "green"
                session_manager.save()
            
        self.log_thought("=== EXECUTION COMPLETE ===")
                
        # 3. RESPOND
        system_persona = (
            "System: You are a helpful AI assistant running on the user's local machine, known as 'End Of Tokens'. "
            "You have just finished processing the user's request using your execution engine. "
            "NEVER say 'I am a language model' or 'I don't have the capability'. "
            "Provide a natural, helpful, and direct final answer based on the execution context. "
            "Do not over-explain your internal processes or how you got the answer unless specifically asked.\n\n"
            f"User Request: {prompt}\n"
            f"Execution Context:\n{chr(10).join(execution_history)}"
        )
        
        if mode == "pro":
            final_answer = controller._run_agy(system_persona, double_check=False)
        else:
            final_answer = controller._run_ollama(system_persona, "llama3.1")
            
        return final_answer
