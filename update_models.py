#!/usr/bin/env python3
"""
Script to update existing agent model names in the database
"""

from app import app, db
from database import Agent

def update_agent_models():
    """Update all agents to use the latest model versions"""
    
    model_updates = {
        # OpenAI models
        'gpt-4-turbo-preview': 'gpt-4o-2024-08-06',
        'gpt-4-vision': 'gpt-4o-2024-08-06',
        'gpt-4-turbo': 'gpt-4o-2024-08-06',
        'gpt-4': 'gpt-4o-2024-08-06',
        
        # Anthropic models
        'claude-3-opus': 'claude-3-5-sonnet-20241022',
        'claude-3-sonnet': 'claude-3-5-sonnet-20241022',
        'claude-3-opus-20240229': 'claude-3-5-sonnet-20241022',
        
        # Google models
        'gemini-pro': 'gemini-1.5-flash',
    }
    
    with app.app_context():
        agents = Agent.query.all()
        updated_count = 0
        
        for agent in agents:
            old_model = agent.model_name
            if old_model in model_updates:
                agent.model_name = model_updates[old_model]
                updated_count += 1
                print(f"Updated {agent.name}: {old_model} -> {agent.model_name}")
        
        if updated_count > 0:
            db.session.commit()
            print(f"\n✅ Successfully updated {updated_count} agents")
        else:
            print("✅ All agents already have the latest model versions")

if __name__ == "__main__":
    update_agent_models()