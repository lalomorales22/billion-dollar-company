"""
AI Provider Integration Module
Handles real API calls to OpenAI, Anthropic, and Google AI
"""

import os
import json
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from config import Config

@dataclass
class AIResponse:
    """Standardized AI response format"""
    content: str
    tokens_used: int
    cost: float
    success: bool
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class AIProvider:
    """Base class for AI providers"""
    
    def __init__(self):
        self.is_configured = False
        
    def generate(self, prompt: str, system_prompt: Optional[str] = None, 
                temperature: float = 0.7, max_tokens: int = 2000) -> AIResponse:
        """Generate a response from the AI provider"""
        raise NotImplementedError

class OllamaProvider(AIProvider):
    """Ollama Local AI Integration"""
    
    # No pricing for local models
    INPUT_PRICE = 0.0
    OUTPUT_PRICE = 0.0
    
    def __init__(self):
        super().__init__()
        self.base_url = "http://localhost:11434"
        self.is_configured = True  # Always configured for local use
        self.timeout = 600  # 10 minutes for local model processing
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                temperature: float = 0.7, max_tokens: int = 2000,
                model: str = "gpt-oss:20b") -> AIResponse:
        """Generate response using Ollama"""
        
        try:
            # Prepare the chat payload
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,  # Disable streaming for simpler response handling
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            # Make request to Ollama API
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API returned status {response.status_code}: {response.text}")
            
            response_data = response.json()
            content = response_data.get("message", {}).get("content", "")
            
            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            full_prompt = (system_prompt or "") + prompt
            input_tokens = len(full_prompt) // 4
            output_tokens = len(content) // 4
            total_tokens = input_tokens + output_tokens
            
            return AIResponse(
                content=content,
                tokens_used=total_tokens,
                cost=0.0,  # Free for local models
                success=True,
                metadata={
                    "model": model,
                    "estimated_input_tokens": input_tokens,
                    "estimated_output_tokens": output_tokens,
                    "ollama_response": response_data
                }
            )
            
        except requests.exceptions.Timeout:
            return AIResponse(
                content="Ollama request timed out. The model may be processing a complex request.",
                tokens_used=0,
                cost=0,
                success=False,
                error_message="Request timeout"
            )
        except requests.exceptions.ConnectionError:
            return AIResponse(
                content="Unable to connect to Ollama. Please ensure Ollama is running on localhost:11434.",
                tokens_used=0,
                cost=0,
                success=False,
                error_message="Connection error"
            )
        except Exception as e:
            return AIResponse(
                content=f"Error calling Ollama API: {str(e)}",
                tokens_used=0,
                cost=0,
                success=False,
                error_message=str(e)
            )



class AIProviderFactory:
    """Factory class to get the Ollama AI provider"""
    
    _ollama_instance = None
    
    @classmethod
    def get_provider(cls, provider_name: str = "ollama") -> AIProvider:
        """Get or create the Ollama AI provider instance"""
        
        if cls._ollama_instance is None:
            cls._ollama_instance = OllamaProvider()
        
        return cls._ollama_instance
    
    @classmethod
    def execute_agent(cls, agent, prompt: str, project_id: Optional[int] = None,
                     task_id: Optional[int] = None) -> Dict[str, Any]:
        """Execute an agent with the appropriate AI provider"""
        
        provider = cls.get_provider(agent.ai_provider)
        
        # Get active system prompt for the agent
        from database import SystemPrompt
        system_prompt = SystemPrompt.query.filter_by(
            agent_id=agent.id,
            is_active=True
        ).first()
        
        system_content = None
        if system_prompt:
            system_content = f"{system_prompt.role}\n\n{system_prompt.instructions}"
        
        # Call the AI provider with correct parameters
        generate_kwargs = {
            'prompt': prompt,
            'system_prompt': system_content,
            'temperature': agent.temperature,
            'max_tokens': agent.max_tokens
        }
        
        # Always use gpt-oss:20b model for Ollama
        generate_kwargs['model'] = 'gpt-oss:20b'
        
        response = provider.generate(**generate_kwargs)
        
        # Create execution record
        from database import db, AgentExecution
        from datetime import datetime
        
        execution = AgentExecution(
            agent_id=agent.id,
            project_id=project_id,
            task_id=task_id,
            input_prompt=prompt,
            output_response=response.content,
            tokens_used=response.tokens_used,
            cost=response.cost,
            duration_ms=0,  # Will be calculated by Celery task
            success=response.success,
            error_message=response.error_message,
            execution_metadata=response.metadata
        )
        db.session.add(execution)
        
        # Update agent statistics
        agent.total_executions += 1
        agent.last_active = datetime.utcnow()
        if response.success:
            agent.success_rate = ((agent.success_rate * (agent.total_executions - 1)) + 100) / agent.total_executions
        else:
            agent.success_rate = (agent.success_rate * (agent.total_executions - 1)) / agent.total_executions
        
        db.session.commit()
        
        return {
            'success': response.success,
            'execution_id': execution.id,
            'response': response.content,
            'tokens_used': response.tokens_used,
            'cost': response.cost,
            'error': response.error_message,
            'metadata': response.metadata or {}
        }