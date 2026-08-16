from playwright.sync_api import sync_playwright
from core.session_manager import global_storage_manager

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    def _ensure_browser(self):
        if not self.playwright:
            self.playwright = sync_playwright().start()
            
            browser_type = global_storage_manager.get("system_settings", "default_browser")
            args = ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-infobars"]
            
            if browser_type == "chrome" or browser_type == "chromium":
                self.browser = self.playwright.chromium.launch(headless=False, args=args)
            elif browser_type == "webkit":
                self.browser = self.playwright.webkit.launch(headless=False)
            else:
                self.browser = self.playwright.firefox.launch(headless=False)
                
            self.page = self.browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            # Remove navigator.webdriver detection flag
            try:
                self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except:
                pass

    def execute_action(self, action: str, args: dict) -> str:
        try:
            if action == "open_url":
                url = args.get("url", "")
                if not url: return "Error: Missing 'url' argument."
                if not url.startswith("http"): url = "https://" + url
                self._ensure_browser()
                self.page.goto(url)
                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass # Timeout on networkidle is fine, page probably mostly loaded
                return f"Successfully opened {url}. Page title: {self.page.title()}"
                
            elif action == "click":
                selector = args.get("selector", "")
                if not selector: return "Error: Missing 'selector' argument."
                self._ensure_browser()
                try:
                    self.page.click(selector, timeout=4000)
                    return f"Successfully clicked '{selector}'."
                except Exception as e:
                    # Smart fallback for search results and links
                    fallbacks = ["h3", "a:has(h3)", "#search a h3", "div#rso a:has(h3)", "div.g a", "div#rso a", "a[href^='http']"]
                    for fb in fallbacks:
                        try:
                            loc = self.page.locator(fb).first
                            if loc.count() > 0:
                                loc.click(timeout=2000)
                                return f"Clicked element matching fallback locator '{fb}' (original selector '{selector}' was not found)."
                        except Exception:
                            continue
                    return f"Error: Could not click '{selector}'. (Details: {str(e)})"
                
            elif action == "type":
                selector = args.get("selector", "")
                text = args.get("text", "")
                submit = args.get("submit", False)
                if not text: return "Error: Missing 'text' argument."
                self._ensure_browser()
                if selector:
                    try:
                        self.page.fill(selector, text, timeout=3000)
                        self.page.keyboard.press("Enter")
                        try:
                            self.page.wait_for_load_state("domcontentloaded", timeout=4000)
                        except:
                            pass
                        return f"Successfully typed '{text}' into {selector}, pressed Enter, and loaded search results."
                    except Exception as e:
                        self.page.keyboard.type(text)
                        self.page.keyboard.press("Enter")
                        try:
                            self.page.wait_for_load_state("domcontentloaded", timeout=4000)
                        except:
                            pass
                        return f"Successfully typed '{text}' directly into active element, pressed Enter, and loaded search results."
                else:
                    self.page.keyboard.type(text)
                    self.page.keyboard.press("Enter")
                    try:
                        self.page.wait_for_load_state("domcontentloaded", timeout=4000)
                    except:
                        pass
                    return f"Successfully typed '{text}' directly into page, pressed Enter, and loaded search results."
                
            elif action == "press":
                key = args.get("key", "")
                if not key: return "Error: Missing 'key' argument."
                self._ensure_browser()
                self.page.keyboard.press(key)
                return f"Successfully pressed {key}."
                
            elif action == "extract_text":
                selector = args.get("selector", "body")
                self._ensure_browser()
                try:
                    try:
                        self.page.wait_for_load_state("domcontentloaded", timeout=4000)
                    except:
                        pass
                    text = self.page.locator(selector).first.inner_text(timeout=5000)
                    cleaned = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
                    if len(cleaned) > 2000:
                        cleaned = cleaned[:2000] + "\n... [truncated]"
                    return f"Extracted text from '{selector}':\n{cleaned}"
                except Exception as e:
                    try:
                        text = self.page.inner_text("body", timeout=3000)
                        cleaned = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
                        if len(cleaned) > 2000:
                            cleaned = cleaned[:2000] + "\n... [truncated]"
                        return f"Extracted text from 'body' (fallback from '{selector}'):\n{cleaned}"
                    except:
                        return f"Error: Could not extract text from '{selector}'. (Details: {str(e)})"
                
            elif action == "get_html":
                self._ensure_browser()
                try:
                    try:
                        self.page.wait_for_load_state("domcontentloaded", timeout=3000)
                    except:
                        pass
                    html = self.page.content()
                except Exception:
                    import time
                    time.sleep(1)
                    html = self.page.content()
                if len(html) > 1500:
                    html = html[:1500] + "... [truncated]"
                return f"HTML content:\n{html}"
                
            elif action == "close":
                return self.close()
            else:
                return f"Error: Unknown browser action '{action}'."
        except Exception as e:
            return f"Browser error during '{action}': {str(e)}"

    def close(self) -> str:
        try:
            if self.page:
                try:
                    self.page.close()
                except Exception:
                    pass
            if self.browser:
                try:
                    self.browser.close()
                except Exception:
                    pass
            if self.playwright:
                try:
                    self.playwright.stop()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self.page = None
            self.browser = None
            self.playwright = None
        return "Browser closed."

browser_manager = BrowserManager()
