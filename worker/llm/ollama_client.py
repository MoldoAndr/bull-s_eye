"""
Bull's Eye - Ollama Cloud API Client
Client for interacting with Ollama Cloud API (https://ollama.com/api)
IMPORTANT: All requests are SEQUENTIAL - no parallel requests allowed
"""

import json
import time
import asyncio
from typing import Optional, Dict, Any, List
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = structlog.get_logger()

# Global lock to ensure sequential requests
_ollama_lock = asyncio.Lock()
_last_request_time = 0.0


class OllamaCloudClient:
    """Client for Ollama Cloud API with Bearer token authentication."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.api_url = settings.ollama_api_url
        self.api_key = api_key or settings.ollama_api_key
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout
        self.logger = structlog.get_logger().bind(component="ollama_cloud")
        
        if not self.api_key:
            raise ValueError("OLLAMA_API_KEY is required for Ollama Cloud API")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with Bearer token authentication."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def _wait_for_rate_limit(self):
        """Ensure minimum delay between requests (sequential only)."""
        global _last_request_time
        
        elapsed = time.time() - _last_request_time
        min_delay = settings.llm_request_delay
        
        if elapsed < min_delay:
            await asyncio.sleep(min_delay - elapsed)
        
        _last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(min=2, max=20),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError))
    )
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        model: Optional[str] = None,
        allow_fallback: bool = True,
    ) -> str:
        """
        Send a chat completion request to Ollama Cloud.
        Uses global lock to ensure sequential requests.
        """
        async with _ollama_lock:
            await self._wait_for_rate_limit()
            
            use_model = model or self.model
            
            payload = {
                "model": use_model,
                "messages": messages,
                "stream": False,
            }
            
            self.logger.debug(
                "Sending chat request",
                model=use_model,
                messages_count=len(messages)
            )
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.post(
                        self.api_url,
                        headers=self._get_headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Extract content from response
                    content = result.get("message", {}).get("content", "")
                    
                    self.logger.debug(
                        "Chat response received",
                        response_length=len(content)
                    )
                    
                    return content
                    
                except httpx.HTTPStatusError as e:
                    self.logger.error(
                        "Ollama Cloud API HTTP error",
                        status_code=e.response.status_code,
                        response_text=e.response.text[:500],
                        model=use_model
                    )
                    # Try fallback to a different model if unauthorized
                    if e.response.status_code == 401 and allow_fallback:
                        self.logger.warning("Unauthorized for model, trying fallback", model=use_model)
                        fallback_models = ["deepseek-v3.2:cloud", "gpt-oss:120b-cloud", "kimi-k2-thinking:cloud"]
                        for fallback in fallback_models:
                            if fallback != use_model:
                                try:
                                    self.logger.info("Attempting fallback model", fallback=fallback)
                                    return await self.chat(messages, temperature, fallback, allow_fallback=False)
                                except Exception as fallback_err:
                                    self.logger.warning("Fallback model failed", fallback=fallback, error=str(fallback_err))
                                    continue
                    # Also handle 404 (model not found)
                    if e.response.status_code == 404 and allow_fallback:
                        self.logger.warning("Model not found, trying fallback", model=use_model)
                        fallback_models = ["deepseek-v3.2:cloud", "gpt-oss:120b-cloud", "kimi-k2-thinking:cloud"]
                        for fallback in fallback_models:
                            if fallback != use_model:
                                try:
                                    self.logger.info("Attempting fallback model", fallback=fallback)
                                    return await self.chat(messages, temperature, fallback, allow_fallback=False)
                                except Exception as fallback_err:
                                    self.logger.warning("Fallback model failed", fallback=fallback, error=str(fallback_err))
                                    continue
                    raise
                except httpx.TimeoutException:
                    self.logger.error("Ollama Cloud API timeout", model=use_model)
                    raise
                except Exception as e:
                    self.logger.error("Ollama Cloud API error", error=str(e))
                    raise
    
    async def analyze_code(
        self,
        code: str,
        file_path: str,
        language: str,
        analysis_type: str = "full",
    ) -> Dict[str, Any]:
        """
        Analyze code and return structured results.
        """
        # Truncate very long files
        max_code_length = 12000
        if len(code) > max_code_length:
            code = code[:max_code_length] + "\n\n... [TRUNCATED - file too large] ..."
        
        system_message = {
            "role": "system",
            "content": """You are an expert code security analyst and software engineer. 
Analyze the provided code thoroughly for:
1. Security vulnerabilities (injection, auth issues, data exposure, etc.)
2. Code quality issues (complexity, maintainability, error handling)
3. Performance concerns
4. Best practice violations

Be specific and actionable. Focus on real issues, not stylistic preferences.
Always respond with valid JSON."""
        }
        
        user_message = {
            "role": "user",
            "content": f"""Analyze this {language} file: `{file_path}`

```{language}
{code}
```

Respond with JSON in this exact format:
{{
    "summary": "Brief 1-2 sentence description of what this file does",
    "purpose": "Main responsibility/purpose of this code",
    "complexity": "low|medium|high",
    "is_entrypoint": true/false,
    "is_test_file": true/false,
    "security_issues": [
        {{
            "severity": "critical|high|medium|low",
            "title": "Issue title",
            "description": "Detailed description",
            "line_hint": "approximate line or code pattern",
            "recommendation": "How to fix it"
        }}
    ],
    "quality_issues": [
        {{
            "severity": "high|medium|low",
            "title": "Issue title",
            "description": "Detailed description",
            "recommendation": "How to fix it"
        }}
    ],
    "positive_aspects": ["list of good practices found in this code"],
    "dependencies_analysis": "Brief analysis of imported dependencies and potential risks"
}}"""
        }
        
        try:
            response = await self.chat([system_message, user_message])
            
            # Try to parse JSON from response
            # Handle markdown code blocks if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            return json.loads(response.strip())
            
        except json.JSONDecodeError as e:
            self.logger.warning(
                "Failed to parse LLM response as JSON",
                file=file_path,
                error=str(e),
                response_preview=response[:500] if response else "empty"
            )
            return {
                "summary": "Analysis completed but response parsing failed",
                "purpose": "Unknown",
                "complexity": "unknown",
                "security_issues": [],
                "quality_issues": [],
                "parse_error": str(e),
                "raw_response": response[:1000] if response else ""
            }
        except Exception as e:
            self.logger.error("Code analysis failed", file=file_path, error=str(e))
            return {
                "summary": f"Analysis failed: {str(e)}",
                "purpose": "Unknown",
                "error": str(e)
            }
    
    async def summarize_component(
        self,
        component_name: str,
        component_path: str,
        file_summaries: List[Dict[str, Any]],
        language: str,
    ) -> Dict[str, Any]:
        """
        Generate a high-level summary of a component based on file analyses.
        """
        # Build a summary of files for context
        files_context = []
        for fs in file_summaries[:20]:  # Limit to 20 files
            files_context.append(f"- {fs.get('path', 'unknown')}: {fs.get('summary', 'No summary')}")
        
        files_text = "\n".join(files_context)
        
        system_message = {
            "role": "system",
            "content": """You are an expert software architect. 
Analyze the component structure and provide high-level insights.
Focus on architecture, security posture, and overall code health.
Always respond with valid JSON."""
        }
        
        user_message = {
            "role": "user",
            "content": f"""Analyze this {language} component: `{component_name}` at path `{component_path}`

Files in this component:
{files_text}

Total files: {len(file_summaries)}

Respond with JSON:
{{
    "summary": "2-3 sentence description of this component's purpose",
    "architecture_type": "module|service|library|utility|config|test",
    "health_score": 0-100,
    "key_responsibilities": ["list of main responsibilities"],
    "security_posture": "Brief assessment of security practices",
    "technical_debt_indicators": ["list of potential tech debt"],
    "recommendations": ["prioritized list of improvements"]
}}"""
        }
        
        try:
            response = await self.chat([system_message, user_message])
            
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            return json.loads(response.strip())
            
        except Exception as e:
            self.logger.error(
                "Component summary failed",
                component=component_name,
                error=str(e)
            )
            return {
                "summary": f"Summary generation failed: {str(e)}",
                "health_score": 50,
                "error": str(e)
            }
    
    async def enrich_finding(
        self,
        finding: Dict[str, Any],
        code_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enrich a scanner finding with LLM explanation and suggestions.
        """
        system_message = {
            "role": "system",
            "content": """You are a security expert. Explain security findings in plain language
and provide actionable remediation advice. Be concise but thorough."""
        }
        
        context_text = ""
        if code_context:
            context_text = f"\n\nCode context:\n```\n{code_context[:2000]}\n```"
        
        user_message = {
            "role": "user",
            "content": f"""Explain this security finding:

Scanner: {finding.get('scanner', 'unknown')}
Rule: {finding.get('rule_id', 'unknown')}
Severity: {finding.get('severity', 'unknown')}
Title: {finding.get('title', 'No title')}
File: {finding.get('file_path', 'unknown')}
Line: {finding.get('line_start', 'unknown')}
Description: {finding.get('description', 'No description')}
{context_text}

Respond with JSON:
{{
    "explanation": "Plain language explanation of why this is a problem",
    "impact": "What could happen if exploited/ignored",
    "fix_suggestion": "Specific code changes or steps to fix",
    "false_positive_likelihood": "low|medium|high",
    "priority": "immediate|high|medium|low"
}}"""
        }
        
        try:
            response = await self.chat([system_message, user_message])
            
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            enrichment = json.loads(response.strip())
            
            # Merge enrichment into finding
            finding["llm_explanation"] = enrichment.get("explanation", "")
            finding["llm_impact"] = enrichment.get("impact", "")
            finding["llm_fix_suggestion"] = enrichment.get("fix_suggestion", "")
            finding["llm_priority"] = enrichment.get("priority", "medium")
            
            return finding
            
        except Exception as e:
            self.logger.warning("Finding enrichment failed", error=str(e))
            return finding
    
    async def generate_executive_summary(
        self,
        job_name: str,
        repo_url: str,
        findings_summary: Dict[str, int],
        component_summaries: List[Dict[str, Any]],
    ) -> str:
        """
        Generate an executive summary report with graceful degradation.
        """
        # Build component context
        components_text = []
        for cs in component_summaries[:10]:
            components_text.append(
                f"- {cs.get('name', 'unknown')}: {cs.get('summary', 'No summary')[:100]}"
            )
        
        system_message = {
            "role": "system",
            "content": "You are a security consultant writing an executive summary for a codebase analysis report. Be professional and concise."
        }
        
        user_message = {
            "role": "user",
            "content": f"""Write an executive summary for this codebase analysis:

Analysis: {job_name}
Repository: {repo_url}

Findings Summary:
- Critical: {findings_summary.get('critical', 0)}
- High: {findings_summary.get('high', 0)}
- Medium: {findings_summary.get('medium', 0)}
- Low: {findings_summary.get('low', 0)}
- Info: {findings_summary.get('info', 0)}
- Total: {findings_summary.get('total', 0)}

Components Analyzed:
{chr(10).join(components_text) if components_text else 'No components analyzed'}

Write a 2-3 paragraph executive summary covering:
1. Overall security posture
2. Key concerns requiring immediate attention
3. General recommendations

Keep it professional and actionable."""
        }
        
        try:
            return await self.chat([system_message, user_message], temperature=0.5, allow_fallback=True)
        except Exception as e:
            self.logger.error("Executive summary generation failed", error=str(e))
            # Provide a meaningful fallback summary
            total = findings_summary.get('total', 0)
            critical = findings_summary.get('critical', 0)
            high = findings_summary.get('high', 0)
            
            severity_assessment = "low risk"
            if critical > 0:
                severity_assessment = "critical risk"
            elif high > 5:
                severity_assessment = "high risk"
            elif high > 0:
                severity_assessment = "moderate risk"
            
            return f"""**Executive Summary**

The analysis of {job_name} has identified {total} security and quality findings across the codebase, indicating a **{severity_assessment}** security posture. The findings include {critical} critical, {high} high, {findings_summary.get('medium', 0)} medium, and {findings_summary.get('low', 0)} low severity issues.

**Key Concerns:** {"Critical vulnerabilities require immediate remediation. " if critical > 0 else ""}{"Multiple high-severity issues should be addressed promptly. " if high > 0 else ""}The identified issues span security, code quality, and best practice violations.

**Recommendations:** Prioritize remediation of critical and high-severity findings, implement automated security scanning in CI/CD, conduct code reviews for security-sensitive changes, and establish secure coding guidelines for the development team.

(Note: This is an automated fallback summary. Full AI-powered analysis was unavailable.)"""


# Convenience function to get client instance
def get_ollama_client(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> OllamaCloudClient:
    """Get an Ollama Cloud client instance."""
    return OllamaCloudClient(api_key=api_key, model=model)
