import time
import json
import re
import subprocess
from core.session_manager import session_manager, global_storage_manager
from core.browser_manager import browser_manager

def extract_json_objects(text):
    objs = []
    start = None
    depth = 0
    in_string = False
    escape = False
    for idx, ch in enumerate(text):
        if ch == '"' and not escape:
            in_string = not in_string
        elif ch == '\\' and in_string:
            escape = not escape
            continue
        elif not in_string:
            if ch == '{':
                if depth == 0:
                    start = idx
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    candidate = text[start:idx+1]
                    try:
                        objs.append(json.loads(candidate))
                    except:
                        pass
                    start = None
        escape = False
    return objs

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
            "You are 'End Of Tokens', an automated web research and IT automation planner.\n"
            "You are planning automated browser searches to extract publicly available web information. You are NOT giving financial, medical, or legal advice.\n"
            "Break the user's objective into distinct, sequential, simple milestone steps (2 to 4 steps max).\n"
            "Ensure the plan covers the ENTIRE objective from start to finish, including the final extraction, saving, or answering step.\n"
            "Each step must be a concise, single action or goal. For example:\n"
            "[\n"
            "  {\"name\": \"Search Google for 'best budget pc builds'\"},\n"
            "  {\"name\": \"Click on the first search result link\"},\n"
            "  {\"name\": \"Extract and summarize page content\"}\n"
            "]\n\n"
            "CRITICAL: If the user request is a general question or conversation (no browser/system actions needed), output: [{\"name\": \"Directly answer user query\"}].\n"
            "Otherwise, output ONLY the raw JSON array of step objects.\n\n"
            f"User Objective: {prompt}"
        )
        try:
            plan_response = controller._run_ollama(plan_prompt, "llama3.1")
            plan_response = re.sub(r'```json\n?', '', plan_response)
            plan_response = re.sub(r'```\n?', '', plan_response)
            
            plan_data = None
            # Extract JSON list using regex or json parser
            match = re.search(r'\[\s*\{.*?\}\s*\]', plan_response.strip(), re.DOTALL)
            if match:
                try:
                    plan_data = json.loads(match.group(0))
                except:
                    pass
            
            if not plan_data:
                match_arr = re.search(r'\[.*?\]', plan_response.strip(), re.DOTALL)
                if match_arr:
                    try:
                        plan_data = json.loads(match_arr.group(0))
                    except:
                        pass
            
            if not plan_data:
                plan_data = json.loads(plan_response.strip())
            
            if not isinstance(plan_data, list) or len(plan_data) == 0:
                raise ValueError("Parsed plan is empty or not a list")
            
            parsed_plan = []
            for item in plan_data:
                if isinstance(item, dict):
                    name_val = item.get("name") or item.get("step") or item.get("action") or str(item)
                    parsed_plan.append({"name": str(name_val), "status": "grey"})
                elif isinstance(item, str) and item.strip():
                    parsed_plan.append({"name": item.strip(), "status": "grey"})
                else:
                    parsed_plan.append({"name": str(item), "status": "grey"})
                    
            self.session.plan = parsed_plan
            session_manager.save()
        except Exception:
            clean_query = prompt.replace("\"", "").replace("'", "")[:40].strip()
            self.session.plan = [
                {"name": f"Search online for '{clean_query}'", "status": "grey"},
                {"name": f"Open top search result for '{clean_query}'", "status": "grey"},
                {"name": "Extract and summarize findings", "status": "grey"}
            ]
        
        session_manager.save()
        turbo_mode = self.session.settings.get("turbo_mode", False)
        persistence_mode = self.session.settings.get("persistence_mode", False)
        double_check_mode = self.session.settings.get("double_check", False)
        
        # Track history for ReAct loop
        execution_history = []
        
        # 2. EXECUTE
        task_failed_message = None
        current_step_idx = 0
        try:
            while current_step_idx < len(self.session.plan):
                if api.abort_flag:
                    self.log_thought("❌ Task aborted by user.")
                    break
                
                step = self.session.plan[current_step_idx]
                self.session.plan[current_step_idx]["status"] = "yellow"
                session_manager.save()
                self.log_thought(f"--- STEP {current_step_idx+1}: {step['name']} ---")
                
                step_attempts = 0
                step_completed = False
                max_attempts = float('inf') if persistence_mode else 8
                last_action_key = None
                repeat_count = 0
                
                while step_attempts < max_attempts and not step_completed:
                    if api.abort_flag:
                        break
                    step_attempts += 1
                    
                    # Ask LLM what to do
                    history_text = "\n".join(execution_history) if execution_history else "None"
                    local_storage_str = json.dumps(self.session.local_storage, indent=2)
                    global_toc_str = json.dumps(global_storage_manager.get_toc(), indent=2)
                    
                    action_prompt = (
                        "You are 'End Of Tokens', an autonomous IT web automation agent operating browser tools.\n"
                        "You are performing general web searches and extracting public online content. You are NOT providing professional financial, medical, or legal advice.\n\n"
                        f"Overall User Objective: {prompt}\n"
                        f"TARGET GOAL FOR CURRENT STEP: {step['name']}\n\n"
                        "CRITICAL RULES:\n"
                        f"1. Your current job is to accomplish ONLY '{step['name']}'.\n"
                        f"2. As soon as '{step['name']}' is achieved or if previous actions already accomplished it, you MUST output: {{\"action\": \"finish_step\", \"args\": {{\"message\": \"done\"}}}}\n"
                        "3. Do NOT repeat an action if it already succeeded in Execution History.\n"
                        "4. Output strictly ONE valid JSON object. Never output conversational refusals, disclaimers, or text outside JSON.\n\n"
                        "=== ACTIONS SCHEMA ===\n"
                        "Output exactly ONE JSON object (no comments, strictly valid JSON):\n"
                        "{\n"
                        "  \"action\": \"<finish_step | browser_action | shell_exec | thought | store_memory | retrieve_memory | fail_step>\",\n"
                        "  \"args\": {<action_specific_args>},\n"
                        "  \"reason\": \"<why you are doing this>\"\n"
                        "}\n\n"
                        "Action Reference:\n"
                        f"- finish_step: Mark '{step['name']}' as DONE. args: {{\"message\": \"<summary>\"}}\n"
                        "- browser_action: Control browser. args must include 'command':\n"
                        "    * open_url: args: {\"command\": \"open_url\", \"url\": \"https://...\"}\n"
                        "    * type: args: {\"command\": \"type\", \"text\": \"...\"} (Automatically submits and presses Enter!)\n"
                        "    * click: args: {\"command\": \"click\", \"selector\": \"...\"} (For search results, use 'h3' or 'a:has(h3)')\n"
                        "    * extract_text: args: {\"command\": \"extract_text\", \"selector\": \"body\"}\n"
                        "    * press: args: {\"command\": \"press\", \"key\": \"Enter\"}\n"
                        "    * get_html: args: {\"command\": \"get_html\"}\n"
                        "    * close: args: {\"command\": \"close\"}\n"
                        "- shell_exec: Run a CMD command. args: {\"command\": \"...\"}.\n"
                        "- store_memory: Save to knowledge base. args: {\"scope\": \"global\"|\"local\", \"category\": \"...\", \"key\": \"...\", \"value\": \"...\"}\n"
                        "- retrieve_memory: Read memory. args: {\"scope\": \"global\"|\"local\", \"category\": \"...\", \"key\": \"...\"}\n"
                        "- thought: Internal reasoning. args: {\"message\": \"...\"}\n\n"
                        "=== STORAGE ===\n"
                        f"Global TOC: {global_toc_str}\n"
                        f"Local Storage: {local_storage_str}\n\n"
                        f"Execution History so far:\n{history_text}"
                    )
                    
                    action_response = controller._run_ollama(action_prompt, "llama3.1")
                    action_response = re.sub(r'```json\n?', '', action_response)
                    action_response = re.sub(r'```\n?', '', action_response)
                    
                    action_objects = extract_json_objects(action_response)
                    action_data = None
                    
                    if action_objects:
                        # If Llama included multiple JSON blocks (e.g. conversational wrap), look for finish_step or valid action
                        for obj in action_objects:
                            if isinstance(obj, dict) and obj.get("action") == "finish_step":
                                action_data = obj
                                break
                        if not action_data:
                            for obj in reversed(action_objects):
                                if isinstance(obj, dict) and "action" in obj:
                                    action_data = obj
                                    break
                        if not action_data and isinstance(action_objects[0], dict):
                            action_data = action_objects[0]
                    
                    if not action_data:
                        # Fallback regex parse attempt
                        try:
                            match = re.search(r'\{.*\}', action_response.strip(), re.DOTALL)
                            if match:
                                action_data = json.loads(match.group(0))
                        except:
                            pass
                    
                    if not action_data:
                        self.log_thought(f"⚠️ Invalid JSON received from agent. Retrying ({step_attempts}/{max_attempts})...\nRaw: {action_response[:100]}")
                        execution_history.append("[System Directive]: You are an automated browser agent performing web queries. You MUST respond with ONLY a single raw JSON object matching the ACTIONS SCHEMA (e.g. action: 'browser_action', args: {'command': 'type', 'text': '...'}). Do not output refusal or conversational commentary.")
                        continue
                        
                    action_type = action_data.get("action")
                    args = action_data.get("args", {})
                    reason = action_data.get("reason", "")
                    
                    # Auto-normalize browser action aliases (e.g. action: "extract_text" -> action: "browser_action", command: "extract_text")
                    if action_type in ["open_url", "click", "type", "press", "extract_text", "get_html", "close"]:
                        if not isinstance(args, dict): args = {}
                        args["command"] = action_type
                        action_type = "browser_action"
                    
                    if not action_type:
                        self.log_thought(f"⚠️ Missing 'action' key in response. Retrying ({step_attempts}/{max_attempts})...")
                        continue
                        
                    self.log_thought(f"Action: {action_type} | Reason: {reason}")
                    
                    # Check for repeated identical actions that already succeeded
                    action_key = f"{action_type}:{json.dumps(args, sort_keys=True)}"
                    if action_key == last_action_key and action_type in ["browser_action", "shell_exec"]:
                        repeat_count += 1
                        if repeat_count >= 2:
                            self.log_thought(f"⚠️ Action '{action_type}' was already completed successfully. Auto-finishing step '{step['name']}'.\n")
                            execution_history.append(f"[Agent Completed Step]: Step '{step['name']}' accomplished.")
                            step_completed = True
                            break
                        else:
                            self.log_thought(f"⚠️ Action was already executed. Directing agent to finalize step.\n")
                            execution_history.append(f"[SYSTEM WARNING]: You already executed this exact action successfully! DO NOT repeat it. If '{step['name']}' is done, output: {{\"action\": \"finish_step\", \"args\": {{\"message\": \"done\"}}}}.")
                            continue
                    
                    if action_type == "finish_step":
                        msg = args.get("message", "")
                        
                        # Double Check Verification & Plan Revision Logic
                        if double_check_mode:
                            self.log_thought(f"🔍 [Double Check]: Verifying step '{step['name']}' and auditing plan...")
                            upcoming_steps = [s["name"] for s in self.session.plan[current_step_idx + 1:]]
                            upcoming_str = json.dumps(upcoming_steps)
                            
                            verify_prompt = (
                                "You are a strict QA verification inspector and task strategist for an AI web automation agent.\n"
                                "You are inspecting web automation and information retrieval actions. You are NOT evaluating personal financial/medical advice.\n\n"
                                f"Overall Objective: {prompt}\n"
                                f"Current Step: {step['name']}\n"
                                f"Proposed Completion Summary: {msg}\n"
                                f"Remaining Upcoming Steps (Train Plan): {upcoming_str}\n\n"
                                f"Execution History:\n{history_text}\n\n"
                                "VERIFICATION CRITERIA:\n"
                                "- If the step is to 'Search', it is NOT complete if only a blank homepage (like google.com) was opened. The search query MUST have been typed or search results loaded!\n"
                                "- If the step is to 'Click', it is NOT complete if no search result or target link was successfully clicked.\n"
                                "- If the step is to 'Extract', it is NOT complete if no content was extracted.\n\n"
                                "TASKS:\n"
                                "1. VERIFY: Confirm if the goal of the Current Step was ACTUALLY achieved according to the criteria above.\n"
                                "2. REVISE PLAN: Based on what has been accomplished or discovered so far, decide if the upcoming steps need to be revised (e.g. if future steps are already completed, redundant, missing crucial follow-ups, or need adjusting).\n\n"
                                "Output strictly ONE raw JSON object with this schema (no comments):\n"
                                "{\n"
                                "  \"verified\": true or false,\n"
                                "  \"reason\": \"<detailed reason for pass/fail>\",\n"
                                "  \"correction_guidance\": \"<specific action to take if verified is false>\",\n"
                                "  \"revise_plan\": true or false,\n"
                                "  \"revised_upcoming_steps\": [\"step name 1\", \"step name 2\"]\n"
                                "}"
                            )
                            try:
                                verify_response = controller._run_ollama(verify_prompt, "llama3.1")
                                verify_objs = extract_json_objects(verify_response)
                                verify_data = None
                                if verify_objs and isinstance(verify_objs[0], dict):
                                    verify_data = verify_objs[0]
                                else:
                                    match = re.search(r'\{.*\}', verify_response.strip(), re.DOTALL)
                                    if match:
                                        verify_data = json.loads(match.group(0))
                            except Exception:
                                verify_data = None
                                
                            if verify_data and isinstance(verify_data, dict):
                                is_verified = verify_data.get("verified", True)
                                v_reason = verify_data.get("reason", "Verification completed.")
                                v_guidance = verify_data.get("correction_guidance", "")
                                
                                if not is_verified:
                                    self.log_thought(f"❌ [Double Check FAILED]: {v_reason}\nRequired fix: {v_guidance}\n")
                                    execution_history.append(f"[Double Check FAILED]: Step '{step['name']}' is NOT complete yet. Reason: {v_reason}. You must fix this: {v_guidance}")
                                    continue
                                else:
                                    self.log_thought(f"✅ [Double Check PASSED]: {v_reason}\n")
                                    execution_history.append(f"[Double Check PASSED]: {v_reason}")
                                    
                                    # Handle Dynamic Plan Revision
                                    if verify_data.get("revise_plan", False):
                                        new_upcoming = verify_data.get("revised_upcoming_steps", [])
                                        if isinstance(new_upcoming, list) and len(new_upcoming) > 0:
                                            formatted_new_steps = []
                                            for item in new_upcoming:
                                                if isinstance(item, dict) and "name" in item:
                                                    formatted_new_steps.append({"name": str(item["name"]), "status": "grey"})
                                                elif isinstance(item, str) and item.strip():
                                                    formatted_new_steps.append({"name": item.strip(), "status": "grey"})
                                            
                                            if formatted_new_steps:
                                                self.session.plan = self.session.plan[:current_step_idx + 1] + formatted_new_steps
                                                session_manager.save()
                                                names_list = " ➔ ".join([s["name"] for s in formatted_new_steps])
                                                self.log_thought(f"🔄 [Train Plan Dynamically Revised]: Upcoming steps updated to:\n{names_list}\n")
                                                execution_history.append(f"[Plan Revised]: Upcoming steps updated to: {names_list}")
                            else:
                                self.log_thought("✅ [Double Check]: Verification step completed.\n")
                        
                        if msg:
                            self.log_thought(f"Agent Final Message: {msg}\n")
                            execution_history.append(f"[Agent Completed Step]: {msg}")
                        self.log_thought(f"Agent concluded step is DONE.\n")
                        step_completed = True
                        break
                        
                    elif action_type == "fail_step":
                        msg = args.get("message", "")
                        self.log_thought(f"Agent concluded step FAILED. Reason: {msg}\n")
                        break
                        
                    elif action_type == "thought":
                        msg = args.get("message", "")
                        self.log_thought(f"> Thought: {msg}\n")
                        execution_history.append(f"[Thought]: {msg}")
                        
                    elif action_type == "store_memory":
                        scope = args.get("scope", "local")
                        cat = args.get("category", "General")
                        key = args.get("key", "")
                        val = args.get("value", "")
                        if scope == "global":
                            global_storage_manager.set(cat, key, val)
                            msg = f"Saved to Global Storage [{cat} -> {key}]"
                        else:
                            if cat not in self.session.local_storage:
                                self.session.local_storage[cat] = {}
                            self.session.local_storage[cat][key] = val
                            session_manager.save()
                            msg = f"Saved to Local Storage [{cat} -> {key}]"
                        
                        self.log_thought(f"> {msg}\n")
                        execution_history.append(f"[Storage]: {msg}")
                        
                    elif action_type == "retrieve_memory":
                        scope = args.get("scope", "local")
                        cat = args.get("category", "General")
                        key = args.get("key", "")
                        
                        if scope == "global":
                            val = global_storage_manager.get(cat, key)
                        else:
                            val = self.session.local_storage.get(cat, {}).get(key, None)
                            
                        if val:
                            msg = f"Retrieved [{cat} -> {key}]: {val}"
                        else:
                            msg = f"Retrieved [{cat} -> {key}]: Not Found."
                        
                        self.log_thought(f"> {msg}\n")
                        execution_history.append(f"[Storage retrieval]: {msg}")
                        
                    elif action_type == "shell_exec":
                        command = args.get("command", "")
                        if not command:
                            self.log_thought("⚠️ Empty command provided.")
                            continue
                            
                        self.log_thought(f"> {command}")
                        
                        # Check Approval
                        if not turbo_mode:
                            approved = api.request_approval(command, reason)
                            if api.abort_flag: break
                            if not approved:
                                self.log_thought(f"❌ User DENIED execution.\n")
                                execution_history.append(f"> {command}\n[User Denied Execution. You MUST try a completely different command or approach.]")
                                continue
                        
                        # Execute Command
                        try:
                            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
                            stdout = result.stdout.strip()
                            stderr = result.stderr.strip()
                            output = stdout if stdout else stderr
                            if not output: output = "[No Output]"
                            last_action_key = action_key
                            self.log_thought(f"[Output]:\n{output}\n")
                            execution_history.append(f"> {command}\n{output}\n[SYSTEM WARNING: Command succeeded! Do NOT repeat this command. If '{step['name']}' is met, you MUST output EXACTLY: {{\"action\": \"finish_step\", \"args\": {{\"message\": \"done\"}}}}]")
                        except subprocess.TimeoutExpired:
                            last_action_key = None
                            self.log_thought(f"[Output]: ❌ Timeout after 15s\n")
                            execution_history.append(f"> {command}\nTimeout error.")
                        except Exception as e:
                            last_action_key = None
                            self.log_thought(f"[Output]: ❌ Error: {str(e)}\n")
                            execution_history.append(f"> {command}\nError: {str(e)}")
                            
                    elif action_type == "browser_action":
                        command = args.get("command", "")
                        if not command:
                            self.log_thought("⚠️ Empty browser command provided.")
                            continue
                            
                        self.log_thought(f"> [Browser] {command}")
                        
                        # Prevent redundant text extraction in the same step
                        if command == "extract_text" and last_action_key and "extract_text" in last_action_key:
                            self.log_thought(f"Page content was already extracted in this step. Concluding step '{step['name']}'.\n")
                            execution_history.append(f"[Agent Completed Step]: Extracted page content.")
                            step_completed = True
                            break
                        
                        # Check Approval
                        if not turbo_mode:
                            if not self.session.local_storage.get("browser_approved", False):
                                approved = api.request_approval(f"Browser: {command}", reason)
                                if api.abort_flag: break
                                if not approved:
                                    self.log_thought(f"❌ User DENIED browser execution.\n")
                                    execution_history.append(f"> [Browser] {command}\n[User Denied Execution.]")
                                    continue
                                self.session.local_storage["browser_approved"] = True
                                session_manager.save()
                        
                        try:
                            result = browser_manager.execute_action(command, args)
                            self.log_thought(f"[Browser Output]:\n{result}\n")
                            
                            is_success = not result.startswith("Error") and not result.startswith("Browser error")
                            if is_success:
                                last_action_key = action_key
                                
                                # Smart step completion directives
                                sname = step['name'].lower()
                                url_arg = str(args.get("url", "")).lower()
                                
                                if command == "type" and any(w in sname for w in ["search", "type", "input"]):
                                    step_hint = f"[SYSTEM DIRECTIVE: Search query submitted! Step '{step['name']}' is COMPLETE. You MUST output {{\"action\": \"finish_step\", \"args\": {{\"message\": \"Search query submitted\"}}}} next!]"
                                elif command == "open_url" and ("/search" in url_arg or "?q=" in url_arg):
                                    step_hint = f"[SYSTEM DIRECTIVE: Search results page loaded! Step '{step['name']}' is COMPLETE. You MUST output {{\"action\": \"finish_step\", \"args\": {{\"message\": \"Search completed\"}}}} next!]"
                                elif command == "open_url" and "google.com" in url_arg and any(w in sname for w in ["search", "find", "query"]):
                                    step_hint = f"[SYSTEM DIRECTIVE: You are on the Google homepage. Now output action 'browser_action' with command 'type' to type your search query!]"
                                elif command == "open_url" and any(w in sname for w in ["open", "navigate", "go to"]) and not any(w in sname for w in ["search", "find"]):
                                    step_hint = f"[SYSTEM DIRECTIVE: Target page opened! Step '{step['name']}' is COMPLETE. You MUST output {{\"action\": \"finish_step\", \"args\": {{\"message\": \"Page opened\"}}}} next!]"
                                elif command == "click" and "click" in sname:
                                    step_hint = f"[SYSTEM DIRECTIVE: Link clicked! Step '{step['name']}' is COMPLETE. You MUST output {{\"action\": \"finish_step\", \"args\": {{\"message\": \"Clicked link\"}}}} next!]"
                                elif command == "extract_text" and any(w in sname for w in ["extract", "read", "summarize", "content"]):
                                    step_hint = f"[SYSTEM DIRECTIVE: Content extracted! Step '{step['name']}' is COMPLETE. You MUST output {{\"action\": \"finish_step\", \"args\": {{\"message\": \"Extracted content successfully\"}}}} next!]"
                                else:
                                    step_hint = f"[SYSTEM: Command succeeded! If '{step['name']}' is accomplished, output: {{\"action\": \"finish_step\", \"args\": {{\"message\": \"done\"}}}}]"
                            else:
                                last_action_key = None
                                step_hint = f"[SYSTEM: Action returned error. Try an alternative selector or approach.]"
                                
                            execution_history.append(f"> [Browser] {command}\n{result}\n{step_hint}")
                        except Exception as e:
                            last_action_key = None
                            self.log_thought(f"[Browser Output]: ❌ Error: {str(e)}\n")
                            execution_history.append(f"> [Browser] {command}\nError: {str(e)}")
                
                # Step loop ended
                if api.abort_flag:
                    break
                    
                if not step_completed:
                    self.session.plan[current_step_idx]["status"] = "red"
                    self.session.plan[current_step_idx]["name"] = f"{self.session.plan[current_step_idx]['name']} (Failed)"
                    session_manager.save()
                    self.log_thought(f"❌ Step Failed after {step_attempts} attempts.")
                    task_failed_message = f"⚠️ Task Failed: The agent was unable to complete the step '{step['name']}'."
                    break
                else:
                    self.session.plan[current_step_idx]["status"] = "green"
                    session_manager.save()
                    current_step_idx += 1
        finally:
            # Guaranteed cleanup: Close browser and any automated processes upon task end
            try:
                if browser_manager.browser:
                    self.log_thought("🧹 Cleaning up: Closing browser and active automation processes...\n")
                    browser_manager.execute_action("close", {})
            except Exception:
                pass
                
        if task_failed_message:
            return task_failed_message
            
        self.log_thought("=== EXECUTION COMPLETE ===")
                
        # 3. RESPOND
        system_persona = (
            "System: You are a helpful AI assistant running on the user's local machine, known as 'End Of Tokens'. "
            "You have just finished processing the user's request using your execution engine. "
            "NEVER say 'I am a language model' or 'I don't have the capability'. "
            "CRITICAL: Do NOT output JSON in your final answer. Provide a natural, well-formatted Markdown response strictly summarizing the results from the execution context below.\n\n"
            f"User Request: {prompt}\n"
            f"Execution Context:\n{chr(10).join(execution_history)}"
        )
        
        final_answer = controller._run_ollama(system_persona, "llama3.1")
        
        # Clean up any residual JSON envelope from final response if present
        if final_answer.strip().startswith("{") and final_answer.strip().endswith("}"):
            try:
                parsed_ans = json.loads(final_answer.strip())
                if isinstance(parsed_ans, dict):
                    final_answer = parsed_ans.get("message") or parsed_ans.get("args", {}).get("message") or final_answer
            except:
                pass
        
        self.log_thought("=== EXECUTION COMPLETE ===")
        return final_answer
