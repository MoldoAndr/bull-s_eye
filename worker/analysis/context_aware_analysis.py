"""
Bull's Eye - Enhanced Context-Aware Analysis
Solution for true codebase understanding with cross-file context
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
from pathlib import Path
from llm.ollama_client import parse_llm_json_response

@dataclass
class CodebaseContext:
    """Maintains context across the entire codebase analysis."""
    
    # Global context
    project_structure: Dict[str, Any] = None
    component_relationships: Dict[str, List[str]] = None
    import_graph: Dict[str, List[str]] = None
    api_endpoints: List[Dict] = None
    data_models: List[Dict] = None
    
    # Conversation memory per component
    component_memories: Dict[str, List[Dict]] = None
    
    # Cross-file dependencies
    file_dependencies: Dict[str, List[str]] = None
    shared_utilities: List[str] = None
    
    def __post_init__(self):
        if self.component_memories is None:
            self.component_memories = {}
        if self.file_dependencies is None:
            self.file_dependencies = {}
        if self.import_graph is None:
            self.import_graph = {}

class ContextAwareAnalyzer:
    """Enhanced analyzer with cross-file context and memory."""
    
    def __init__(self, ollama_client):
        self.ollama = ollama_client
        self.context = CodebaseContext()
        self.analysis_memory = {}  # Store previous analyses
    
    async def build_codebase_context(self, components: List[Dict]) -> CodebaseContext:
        """Build comprehensive understanding of the codebase structure."""
        
        # 1. Map project structure
        self.context.project_structure = self._map_project_structure(components)
        
        # 2. Extract import relationships
        self.context.import_graph = await self._extract_import_graph(components)
        
        # 3. Identify component relationships
        self.context.component_relationships = self._map_component_relationships()
        
        # 4. Find shared utilities and common patterns
        self.context.shared_utilities = self._find_shared_utilities(components)
        
        return self.context
    
    def _map_project_structure(self, components: List[Dict]) -> Dict[str, Any]:
        """Create a comprehensive map of the project structure."""
        structure = {
            "components": {},
            "languages": set(),
            "entry_points": [],
            "config_files": [],
            "test_components": []
        }
        
        for comp in components:
            comp_name = comp["name"]
            structure["components"][comp_name] = {
                "path": comp["path"],
                "language": comp.get("language"),
                "file_count": comp.get("file_count", 0),
                "component_type": comp.get("component_type"),
                "files": [f["path"] for f in comp.get("files", [])]
            }
            structure["languages"].add(comp.get("language"))
            
            # Identify entry points
            if comp.get("component_type") == "service":
                structure["entry_points"].append(comp_name)
        
        structure["languages"] = list(structure["languages"])
        return structure
    
    async def _extract_import_graph(self, components: List[Dict]) -> Dict[str, List[str]]:
        """Extract import relationships between files."""
        import_graph = {}
        
        for comp in components:
            for file_info in comp.get("files", []):
                file_path = file_info["path"]
                content = self._get_file_content(file_path)
                
                if content:
                    imports = self._extract_imports(content, file_info.get("language"))
                    import_graph[file_path] = imports
        
        return import_graph
    
    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import statements based on language."""
        imports = []
        
        if language == "python":
            import re
            # Python imports
            patterns = [
                r'^from\s+(\S+)\s+import',
                r'^import\s+(\S+)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)
        
        elif language in ["javascript", "typescript"]:
            import re
            # JS/TS imports
            patterns = [
                r'import.*from\s+[\'"]([^\'"]+)[\'"]',
                r'require\([\'"]([^\'"]+)[\'"]\)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content)
                imports.extend(matches)
        
        elif language == "go":
            import re
            # Go imports
            matches = re.findall(r'"([^"]+)"', content)
            imports.extend(matches)
        
        return imports
    
    async def analyze_file_with_context(
        self, 
        file_path: str, 
        content: str, 
        language: str,
        component_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Analyze a file with full codebase context."""
        
        # Build context messages
        context_messages = await self._build_context_messages(file_path, component_context)
        
        # System message with enhanced instructions
        system_message = {
            "role": "system",
            "content": f"""You are an expert software architect and security analyst with deep understanding of the entire codebase.

CONTEXT ABOUT THIS CODEBASE:
{json.dumps(self.context.project_structure, indent=2)}

IMPORT RELATIONSHIPS:
{json.dumps(self.context.import_graph, indent=2)}

COMPONENT RELATIONSHIPS:
{json.dumps(self.context.component_relationships, indent=2)}

Analyze the provided file considering:
1. How it fits into the overall architecture
2. Its relationships with other files/components
3. Security implications in the context of the full system
4. Whether it follows established patterns in this codebase
5. Dependencies and potential security risks from imports

Be specific about cross-file concerns and architectural issues."""
        }
        
        # User message with file content
        user_message = {
            "role": "user",
            "content": f"""Analyze this {language} file: `{file_path}`

```{language}
{content}
```

Consider the codebase context provided. Focus on:
- How this file connects to other parts of the system
- Security implications given the import relationships
- Architectural consistency with the rest of the codebase
- Cross-file dependencies and potential risks

Respond with JSON:
{{
    "summary": "What this file does and its role in the system",
    "architectural_role": "How it fits into the overall design",
    "dependencies": ["List of key dependencies and their security implications"],
    "cross_file_concerns": ["Issues that affect multiple files/components"],
    "security_issues": [
        {{
            "severity": "critical|high|medium|low",
            "title": "Issue title",
            "description": "Detailed description with context",
            "affected_files": ["List of related files that might be impacted"],
            "recommendation": "How to fix it"
        }}
    ],
    "architectural_issues": [
        {{
            "severity": "high|medium|low",
            "title": "Architectural concern",
            "description": "How this affects the overall system design",
            "recommendation": "Suggested architectural improvement"
        }}
    ]
}}"""
        }
        
        # Combine all messages
        messages = context_messages + [system_message, user_message]
        
        try:
            response = await self.ollama.chat(messages)
            
            # Parse and store in memory
            analysis = self._parse_analysis_response(response)
            self.analysis_memory[file_path] = analysis
            
            return analysis
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _build_context_messages(self, file_path: str, component_context: Optional[Dict]) -> List[Dict]:
        """Build context messages from previous analyses."""
        messages = []
        
        # Add component memory if available
        if component_context:
            comp_name = component_context.get("name")
            if comp_name in self.context.component_memories:
                messages.extend(self.context.component_memories[comp_name])
        
        # Add related file analyses
        related_files = self._get_related_files(file_path)
        for related_file in related_files:
            if related_file in self.analysis_memory:
                analysis = self.analysis_memory[related_file]
                context_msg = {
                    "role": "assistant",
                    "content": f"Related file analysis ({related_file}):\n{json.dumps(analysis, indent=2)}"
                }
                messages.append(context_msg)
        
        return messages
    
    def _get_related_files(self, file_path: str) -> List[str]:
        """Find files related to the current file."""
        related = []
        
        # Files that import this file
        for other_file, imports in self.context.import_graph.items():
            if any(file_path in imp for imp in imports):
                related.append(other_file)
        
        # Files this file imports
        if file_path in self.context.import_graph:
            related.extend(self.context.import_graph[file_path])
        
        # Files in the same component
        for comp_name, comp_data in self.context.project_structure["components"].items():
            if file_path in comp_data["files"]:
                related.extend(comp_data["files"])
                break
        
        return list(set(related) - {file_path})  # Remove self, deduplicate
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured format."""
        parsed, _ = parse_llm_json_response(response)
        if parsed is not None:
            return parsed

        return {
            "summary": "Failed to parse response",
            "raw_response": response,
            "error": "JSON parsing failed",
        }
    
    async def generate_architectural_summary(self) -> Dict[str, Any]:
        """Generate a comprehensive architectural analysis."""
        
        system_message = {
            "role": "system",
            "content": """You are a senior software architect conducting a comprehensive codebase review.

Based on all the file analyses and the codebase structure, provide:
1. Overall architectural assessment
2. Security posture evaluation
3. Design pattern analysis
4. Technical debt assessment
5. Recommendations for improvements

Focus on systemic issues, not individual file problems."""
        }
        
        # Compile all analyses
        all_analyses = list(self.analysis_memory.values())
        
        user_message = {
            "role": "user",
            "content": f"""Generate a comprehensive architectural summary for this codebase.

PROJECT STRUCTURE:
{json.dumps(self.context.project_structure, indent=2)}

FILE ANALYSES:
{json.dumps(all_analyses, indent=2)}

Respond with JSON:
{{
    "architecture_type": "monolith|microservices|library|framework",
    "overall_health_score": 0-100,
    "security_posture": "excellent|good|fair|poor",
    "key_strengths": ["list of architectural strengths"],
    "critical_concerns": ["list of systemic issues"],
    "technical_debt_areas": ["areas with significant technical debt"],
    "security_risks": ["cross-cutting security concerns"],
    "scalability_assessment": "assessment of scalability",
    "maintainability_assessment": "assessment of maintainability",
    "priority_recommendations": ["ranked list of improvements"]
}}"""
        }
        
        try:
            response = await self.ollama.chat([system_message, user_message])
            return self._parse_analysis_response(response)
        except Exception as e:
            return {"error": str(e)}

# Integration with existing engine
async def enhanced_analysis_engine(components, ollama_client):
    """Enhanced analysis engine with context awareness."""
    analyzer = ContextAwareAnalyzer(ollama_client)
    
    # Step 1: Build codebase context
    await analyzer.build_codebase_context(components)
    
    # Step 2: Analyze files with context
    for comp in components:
        for file_info in comp.get("files", []):
            file_path = file_info["path"]
            content = analyzer._get_file_content(file_path)
            
            if content and analyzer.should_analyze_with_llm(file_path):
                analysis = await analyzer.analyze_file_with_context(
                    file_path, content, file_info.get("language"), comp
                )
                
                # Store findings in database
                # ... existing database logic ...
    
    # Step 3: Generate architectural summary
    architectural_summary = await analyzer.generate_architectural_summary()
    
    return architectural_summary
