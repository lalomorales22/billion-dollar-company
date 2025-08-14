"""
Celery Tasks for Async Processing
Handles background AI execution and project pipeline processing
"""

import time
from celery import Celery, Task
from celery.result import AsyncResult
from datetime import datetime
from typing import Dict, Any, Optional
import json

from config import Config

# Initialize Celery
celery_app = Celery('billion_dollar_tasks')
celery_app.config_from_object({
    'broker_url': Config.CELERY_BROKER_URL,
    'result_backend': Config.CELERY_RESULT_BACKEND,
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'UTC',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': 600,  # 10 minutes max per task for local models
    'task_soft_time_limit': 570,  # Soft limit at 9.5 minutes
})

class CallbackTask(Task):
    """Task with Socket.IO callback support"""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called on successful task completion"""
        # Emit Socket.IO event if socketio is available
        emit_task_update(task_id, 'completed', retval)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure"""
        emit_task_update(task_id, 'failed', {'error': str(exc)})

def emit_task_update(task_id: str, status: str, data: Any):
    """Emit task update via Socket.IO"""
    try:
        from app import socketio
        socketio.emit('task_update', {
            'task_id': task_id,
            'status': status,
            'data': data
        }, namespace='/tasks')
    except:
        pass  # Socket.IO might not be available in worker context

@celery_app.task(base=CallbackTask, bind=True)
def execute_agent_async(self, agent_id: int, prompt: str, 
                        project_id: Optional[int] = None,
                        task_id: Optional[int] = None,
                        user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Execute an AI agent asynchronously
    """
    start_time = time.time()
    
    # Import here to avoid circular imports
    from app import create_app
    from database import db, Agent, Task, AgentExecution, Project
    from ai_providers import AIProviderFactory
    
    app = create_app()
    
    with app.app_context():
        try:
            # Update task status to processing
            self.update_state(state='PROCESSING', meta={'status': 'Loading agent...'})
            
            # Get the agent
            agent = db.session.get(Agent, agent_id)
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")
            
            # Update agent status
            agent.status = 'running'
            db.session.commit()
            
            # Update task if provided
            if task_id:
                task = db.session.get(Task, task_id)
                if task:
                    task.status = 'processing'
                    task.started_at = datetime.utcnow()
                    db.session.commit()
            
            # Execute the agent
            self.update_state(state='PROCESSING', meta={'status': 'Calling AI provider...'})
            result = AIProviderFactory.execute_agent(
                agent=agent,
                prompt=prompt,
                project_id=project_id,
                task_id=task_id
            )
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Update execution record with duration
            if result.get('execution_id'):
                execution = db.session.get(AgentExecution, result['execution_id'])
                if execution:
                    execution.duration_ms = duration_ms
                    db.session.commit()
            
            # Update task if provided and successful
            if task_id and result['success']:
                task = db.session.get(Task, task_id)
                if task:
                    task.status = 'completed'
                    task.completed_at = datetime.utcnow()
                    task.actual_duration = int(time.time() - start_time)
                    task.output_data = {'response': result['response']}
                    db.session.commit()
            
            # Update project completion percentage if applicable
            if project_id:
                update_project_progress(project_id)
            
            # Reset agent status
            agent.status = 'idle'
            db.session.commit()
            
            # Emit success via Socket.IO
            emit_task_update(self.request.id, 'completed', result, user_id=user_id, project_id=project_id)
            
            return result
            
        except Exception as e:
            # Reset agent status on error
            try:
                agent = db.session.get(Agent, agent_id)
                if agent:
                    agent.status = 'error'
                    db.session.commit()
                
                if task_id:
                    task = db.session.get(Task, task_id)
                    if task:
                        task.status = 'failed'
                        task.error_message = str(e)[:500]  # Limit error message length
                        db.session.commit()
            except:
                pass
            
            raise

@celery_app.task(bind=True)
def process_project_pipeline(self, project_id: int, stage: int, user_id: int = None) -> Dict[str, Any]:
    """
    Process a project through its pipeline stages
    """
    from app import create_app
    from database import db, Project, Agent, Task
    
    app = create_app()
    
    with app.app_context():
        project = db.session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Get existing tasks for this stage, or create new ones if none exist
        existing_tasks = Task.query.filter_by(project_id=project_id, stage=stage).all()
        
        if existing_tasks:
            # Use existing tasks
            tasks_to_process = existing_tasks
        else:
            # Create new tasks for this stage
            agents = Agent.query.filter_by(stage=stage, is_active=True).all()
            tasks_to_process = []
            for agent in agents:
                task = Task(
                    project_id=project_id,
                    agent_id=agent.id,
                    title=f"{agent.name} - Stage {stage}",
                    description=f"Automated task for {agent.name}",
                    stage=stage,
                    status='pending'
                )
                db.session.add(task)
                tasks_to_process.append(task)
            db.session.commit()
        
        results = []
        for task in tasks_to_process:
            agent = task.assigned_agent
            if not agent:
                continue
                
            self.update_state(state='PROCESSING', 
                            meta={'status': f'Running {agent.name}...'})
            
            # Skip if task is already completed
            if task.status == 'completed':
                continue

            # Emit a task update event
            emit_task_update(task.id, 'processing', {
                'id': task.id,
                'title': task.title,
                'status': 'processing',
                'stage': task.stage,
                'agent': {
                    'icon': agent.icon,
                    'name': agent.name
                }
            }, user_id=user_id, project_id=project_id)
            
            # Execute the agent directly (like artifact generation does)
            try:
                from ai_providers import AIProviderFactory
                
                # Update task status
                task.status = 'processing'
                task.started_at = datetime.utcnow()
                db.session.commit()
                
                # Execute the agent directly
                result = AIProviderFactory.execute_agent(
                    agent=agent,
                    prompt=project.idea_source,
                    project_id=project_id,
                    task_id=task.id
                )
                
                # Update task with result
                if result['success']:
                    task.status = 'completed'
                    task.completed_at = datetime.utcnow()
                    results.append({
                        'agent': agent.name,
                        'status': 'completed',
                        'execution_id': result.get('execution_id')
                    })
                    
                    # Emit task completed event
                    emit_task_update(task.id, 'completed', {
                        'id': task.id,
                        'title': task.title,
                        'status': 'completed',
                        'stage': task.stage,
                        'agent': {
                            'icon': agent.icon,
                            'name': agent.name
                        }
                    }, user_id=user_id, project_id=project_id)
                else:
                    task.status = 'failed'
                    task.error_message = result.get('error', 'Unknown error')
                    results.append({
                        'agent': agent.name,
                        'status': 'failed',
                        'error': result.get('error', 'Unknown error')
                    })
                    
                    # Emit task failed event
                    emit_task_update(task.id, 'failed', {
                        'id': task.id,
                        'title': task.title,
                        'status': 'failed',
                        'stage': task.stage,
                        'agent': {
                            'icon': agent.icon,
                            'name': agent.name
                        }
                    }, user_id=user_id, project_id=project_id)
                
                db.session.commit()
                
            except Exception as e:
                task.status = 'failed'
                task.error_message = str(e)
                db.session.commit()
                
                # Emit task failed event
                emit_task_update(task.id, 'failed', {
                    'id': task.id,
                    'title': task.title,
                    'status': 'failed',
                    'stage': task.stage,
                    'agent': {
                        'icon': agent.icon,
                        'name': agent.name
                    }
                }, user_id=user_id, project_id=project_id)
                
                results.append({
                    'agent': agent.name,
                    'error': str(e),
                    'status': 'failed'
                })
        
        # Update project stage
        project.stage = stage
        project.updated_at = datetime.utcnow()
        
        # Update status based on stage
        stage_status_map = {
            2: 'validating',
            3: 'developing',
            4: 'marketing',
            5: 'operating',
            6: 'scaling'
        }
        project.status = stage_status_map.get(stage, project.status)
        db.session.commit()
        
        return {
            'project_id': project_id,
            'stage': stage,
            'agents_triggered': len(results),
            'results': results
        }

@celery_app.task
def update_project_progress(project_id: int) -> float:
    """
    Update project completion percentage based on completed tasks
    """
    from app import create_app
    from database import db, Project, Task
    
    app = create_app()
    
    with app.app_context():
        project = db.session.get(Project, project_id)
        if not project:
            return 0
        
        total_tasks = Task.query.filter_by(project_id=project_id).count()
        completed_tasks = Task.query.filter_by(
            project_id=project_id,
            status='completed'
        ).count()
        
        if total_tasks > 0:
            completion = (completed_tasks / total_tasks) * 100
            project.completion_percentage = round(completion, 2)
            db.session.commit()
            return completion
        
        return 0

@celery_app.task
def generate_project_artifacts(project_id: int, artifact_type: str) -> Dict[str, Any]:
    """
    Generate project artifacts (code, documentation, etc.)
    """
    from app import create_app
    from database import db, Project, ProjectArtifact, Agent
    from ai_providers import AIProviderFactory
    
    app = create_app()
    
    with app.app_context():
        project = db.session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Select appropriate agent based on artifact type
        agent_map = {
            'code': 'Full-Stack Dev',
            'design': 'UI/UX Designer',
            'documentation': 'Technical Architect',
            'marketing': 'Content Marketing'
        }
        
        agent_name = agent_map.get(artifact_type, 'Full-Stack Dev')
        agent = Agent.query.filter_by(name=agent_name).first()
        
        if not agent:
            raise ValueError(f"Agent {agent_name} not found")
        
        # Generate artifact content
        prompt = f"""
        Generate {artifact_type} for the following project:
        Name: {project.name}
        Description: {project.description}
        Idea: {project.idea_source}
        
        Please provide a complete and production-ready {artifact_type}.
        """
        
        result = AIProviderFactory.execute_agent(
            agent=agent,
            prompt=prompt,
            project_id=project_id
        )
        
        if result['success']:
            # Save artifact
            artifact = ProjectArtifact(
                project_id=project_id,
                type=artifact_type,
                name=f"{project.name} - {artifact_type}",
                description=f"AI-generated {artifact_type}",
                content=result['response'],
                created_by_agent_id=agent.id
            )
            db.session.add(artifact)
            db.session.commit()
            
            return {
                'success': True,
                'artifact_id': artifact.id,
                'content_preview': result['response'][:500]
            }
        
        return {
            'success': False,
            'error': str(result.get('error', 'Unknown error'))
        }

@celery_app.task
def auto_run_project(project_id: int, user_id: int) -> Dict[str, Any]:
    """
    Auto-run a project through all stages with appropriate delays
    """
    from app import create_app
    from database import db, Project, Agent, Task
    from ai_providers import AIProviderFactory
    from datetime import datetime
    import time
    
    app = create_app()
    
    with app.app_context():
        project = db.session.get(Project, project_id)
        if not project or project.user_id != user_id:
            return {'success': False, 'error': 'Project not found or access denied'}
        
        results = []
        
        # Process stages 1-6
        for stage in range(1, 7):
            if project.stage >= stage:
                continue  # Skip if already at this stage or beyond
            
            try:
                # Update project stage
                project.stage = stage
                db.session.commit()
                
                # Process this stage directly (avoid nested Celery tasks)
                # Execute the pipeline logic directly without Celery
                
                # Get existing tasks for this stage, or create new ones if none exist
                existing_tasks = Task.query.filter_by(project_id=project_id, stage=stage).all()
                
                if existing_tasks:
                    # Use existing tasks
                    tasks_to_process = existing_tasks
                else:
                    # Create new tasks for this stage
                    agents = Agent.query.filter_by(stage=stage, is_active=True).all()
                    tasks_to_process = []
                    for agent in agents:
                        task = Task(
                            project_id=project_id,
                            agent_id=agent.id,
                            title=f"{agent.name} - Stage {stage}",
                            description=f"Automated task for {agent.name}",
                            stage=stage,
                            status='pending'
                        )
                        db.session.add(task)
                        tasks_to_process.append(task)
                    db.session.commit()
                
                stage_results = []
                for task in tasks_to_process:
                    agent = task.assigned_agent
                    if not agent:
                        continue
                        
                    # Skip if task is already completed
                    if task.status == 'completed':
                        stage_results.append({
                            'agent': agent.name,
                            'status': 'completed',
                            'execution_id': None
                        })
                        continue

                    # Execute the agent directly
                    try:
                        
                        # Update task status
                        task.status = 'processing'
                        task.started_at = datetime.utcnow()
                        db.session.commit()
                        
                        # Execute the agent directly
                        result = AIProviderFactory.execute_agent(
                            agent=agent,
                            prompt=project.idea_source,
                            project_id=project_id,
                            task_id=task.id
                        )
                        
                        # Update task with result
                        if result['success']:
                            task.status = 'completed'
                            task.completed_at = datetime.utcnow()
                            stage_results.append({
                                'agent': agent.name,
                                'status': 'completed',
                                'execution_id': result.get('execution_id')
                            })
                        else:
                            task.status = 'failed'
                            task.error_message = result.get('error', 'Unknown error')
                            stage_results.append({
                                'agent': agent.name,
                                'status': 'failed',
                                'error': result.get('error', 'Unknown error')
                            })
                        
                        db.session.commit()
                        
                    except Exception as agent_error:
                        task.status = 'failed'
                        task.error_message = str(agent_error)
                        db.session.commit()
                        
                        stage_results.append({
                            'agent': agent.name,
                            'error': str(agent_error),
                            'status': 'failed'
                        })

                # Update project status based on stage
                stage_status_map = {
                    2: 'validating',
                    3: 'developing', 
                    4: 'marketing',
                    5: 'operating',
                    6: 'scaling'
                }
                project.status = stage_status_map.get(stage, project.status)
                project.updated_at = datetime.utcnow()
                db.session.commit()
                
                pipeline_result = {
                    'project_id': project_id,
                    'stage': stage,
                    'agents_triggered': len(stage_results),
                    'results': stage_results
                }
                
                results.append({
                    'stage': stage,
                    'result': pipeline_result,
                    'status': 'completed'
                })
                
                # Wait between stages to allow AI processing to complete
                # Extended delays for local models with slow responses
                if stage < 6:  # Don't wait after the last stage
                    time.sleep(600)  # 10 minute delay between stages
                    
            except Exception as e:
                results.append({
                    'stage': stage,
                    'error': str(e),
                    'status': 'failed'
                })
                break  # Stop auto-run on failure
        
        return {
            'success': True,
            'project_id': project_id,
            'final_stage': project.stage,
            'results': results
        }

# Celery worker command (to be run separately):
# celery -A celery_tasks.celery_app worker --loglevel=info