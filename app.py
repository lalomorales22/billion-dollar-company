from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

from config import Config
from database import db, User, Project, Agent, Task, SystemPrompt, AgentExecution, ProjectArtifact

# Initialize Socket.IO
# Try eventlet first, fall back to threading if not available
# Note: eventlet.monkey_patch() must be called before other imports
# Since we're importing after flask, just use threading mode
async_mode = 'threading'

socketio = SocketIO(cors_allowed_origins="*", async_mode=async_mode)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    socketio.init_app(app)
    
    # Login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    return app

app = create_app()

# Create tables and seed initial data
def init_database():
    with app.app_context():
        db.create_all()
        
        # Check if we need to seed initial agents
        if Agent.query.count() == 0:
            seed_initial_agents()

def seed_initial_agents():
    """Seed the database with initial AI agents based on the landing page"""
    
    agents_data = [
        # Stage 1: Input Processing
        {
            'name': 'Idea Processor',
            'type': 'input',
            'stage': 1,
            'icon': '🧠',
            'color': 'var(--mac-blue)',
            'description': 'Processes and structures initial project ideas',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['idea analysis', 'requirement extraction', 'initial structuring', 'feasibility assessment']
        },
        {
            'name': 'Context Builder',
            'type': 'input',
            'stage': 1,
            'icon': '📋',
            'color': 'var(--mac-green)',
            'description': 'Builds comprehensive context and project scope',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['context gathering', 'scope definition', 'requirement documentation', 'initial planning']
        },
        
        # Stage 2: Validation & Strategy
        {
            'name': 'Market Research',
            'type': 'validation',
            'stage': 2,
            'icon': '📊',
            'color': 'var(--mac-purple)',
            'description': 'Analyzes market size, competitors, and product-market fit',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['market analysis', 'competitor research', 'TAM calculation', 'trend analysis']
        },
        {
            'name': 'Technical Architect',
            'type': 'validation',
            'stage': 2,
            'icon': '🏗️',
            'color': 'var(--mac-teal)',
            'description': 'Designs system architecture and selects tech stack',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['architecture design', 'tech stack selection', 'scalability planning', 'cost estimation']
        },
        
        # Stage 3: Development
        {
            'name': 'UI/UX Designer',
            'type': 'development',
            'stage': 3,
            'icon': '🎨',
            'color': 'var(--mac-purple)',
            'description': 'Creates user interfaces and experiences',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['wireframing', 'UI design', 'UX flows', 'responsive design', 'accessibility']
        },
        {
            'name': 'Full-Stack Dev',
            'type': 'development',
            'stage': 3,
            'icon': '💻',
            'color': 'var(--mac-green)',
            'description': 'Writes frontend and backend code',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['React/Vue/Angular', 'Node.js/Python', 'API development', 'database design']
        },
        {
            'name': 'QA & Security',
            'type': 'development',
            'stage': 3,
            'icon': '🛡️',
            'color': 'var(--mac-pink)',
            'description': 'Automated testing and security scanning',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['unit testing', 'integration testing', 'security audits', 'penetration testing']
        },
        {
            'name': 'DevOps Pipeline',
            'type': 'development',
            'stage': 3,
            'icon': '🚀',
            'color': 'var(--mac-blue)',
            'description': 'CI/CD automation and deployment',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['CI/CD setup', 'containerization', 'auto-scaling', 'monitoring']
        },
        
        # Stage 4: Go-to-Market
        {
            'name': 'Business Setup',
            'type': 'marketing',
            'stage': 4,
            'icon': '🏢',
            'color': 'var(--mac-purple)',
            'description': 'Handles business formation and compliance',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['company formation', 'legal compliance', 'trademark filing', 'terms of service']
        },
        {
            'name': 'Content Marketing',
            'type': 'marketing',
            'stage': 4,
            'icon': '✍️',
            'color': 'var(--mac-orange)',
            'description': 'Creates and distributes content',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['blog writing', 'SEO optimization', 'social media', 'email campaigns']
        },
        {
            'name': 'Sales Automation',
            'type': 'marketing',
            'stage': 4,
            'icon': '💰',
            'color': 'var(--mac-green)',
            'description': 'Automates sales outreach and conversion',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['lead generation', 'email outreach', 'demo scheduling', 'proposal creation']
        },
        
        # Stage 5: Business Operations
        {
            'name': 'Customer Support',
            'type': 'operations',
            'stage': 5,
            'icon': '🤝',
            'color': 'var(--mac-purple)',
            'description': '24/7 intelligent customer service',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['ticket handling', 'live chat', 'knowledge base', 'escalation management']
        },
        {
            'name': 'Analytics Engine',
            'type': 'operations',
            'stage': 5,
            'icon': '📈',
            'color': 'var(--mac-blue)',
            'description': 'Real-time business intelligence',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['KPI tracking', 'predictive analytics', 'reporting', 'anomaly detection']
        },
        {
            'name': 'Finance Manager',
            'type': 'operations',
            'stage': 5,
            'icon': '💳',
            'color': 'var(--mac-green)',
            'description': 'Automated accounting and finance',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['bookkeeping', 'invoicing', 'expense tracking', 'financial forecasting']
        },
        
        # Stage 6: Self-Improvement
        {
            'name': 'System Optimizer',
            'type': 'optimization',
            'stage': 6,
            'icon': '🔧',
            'color': 'var(--mac-red)',
            'description': 'Continuously optimizes all systems',
            'ai_provider': 'ollama',
            'model_name': 'gpt-oss:20b',
            'capabilities': ['performance tuning', 'cost optimization', 'workflow improvement', 'A/B testing']
        }
    ]
    
    for agent_data in agents_data:
        agent = Agent(**agent_data)
        db.session.add(agent)
        
        # Add a default system prompt for each agent
        prompt = SystemPrompt(
            agent=agent,
            name=f"Default prompt for {agent.name}",
            role=f"You are an expert {agent.name} agent responsible for {agent.description}",
            instructions=f"Perform tasks related to {', '.join(agent_data['capabilities'])} with high quality and efficiency.",
            is_active=True
        )
        db.session.add(prompt)
    
    db.session.commit()

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/dashboard')
@login_required
def dashboard():
    projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_at.desc()).limit(10).all()
    agents = Agent.query.filter_by(is_active=True).all()
    
    # Calculate metrics
    total_projects = Project.query.filter_by(user_id=current_user.id).count()
    active_tasks = Task.query.join(Project).filter(
        Project.user_id == current_user.id,
        Task.status.in_(['pending', 'processing'])
    ).count()
    
    recent_executions = AgentExecution.query.join(Project).filter(
        Project.user_id == current_user.id
    ).order_by(AgentExecution.created_at.desc()).limit(10).all()
    
    return render_template('dashboard.html',
                         projects=projects,
                         agents=agents,
                         total_projects=total_projects,
                         active_tasks=active_tasks,
                         recent_executions=recent_executions)

@app.route('/projects')
@login_required
def projects():
    page = request.args.get('page', 1, type=int)
    projects = Project.query.filter_by(user_id=current_user.id).order_by(
        Project.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('projects.html', projects=projects)

@app.route('/projects/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        auto_run = data.get('auto_run') == '1' or data.get('auto_run') is True
        
        project = Project(
            name=data.get('name'),
            description=data.get('description'),
            idea_source=data.get('idea_source'),
            user_id=current_user.id,
            status='idea',
            auto_run=auto_run
        )
        db.session.add(project)
        db.session.commit()
        
        # Create initial tasks for Stage 1: Input Processing and assign to agents
        idea_agent = Agent.query.filter_by(name='Idea Processor').first()
        context_agent = Agent.query.filter_by(name='Context Builder').first()
        
        idea_task = Task(
            project_id=project.id,
            agent_id=idea_agent.id if idea_agent else None,
            title="Process Initial Idea",
            description="AI analysis and structuring of the initial project concept",
            stage=1,
            status='pending'
        )
        db.session.add(idea_task)
        
        context_task = Task(
            project_id=project.id,
            agent_id=context_agent.id if context_agent else None,
            title="Build Project Context",
            description="Comprehensive context gathering and scope definition",
            stage=1,
            status='pending'
        )
        db.session.add(context_task)
        
        db.session.commit()
        
        # Automatically start processing - skip Celery if auto_run is enabled
        celery_available = False
        
        if not auto_run:
            # Only try Celery for non-auto-run projects
            try:
                # Check if Redis is available for async processing
                import redis
                r = redis.from_url(Config.REDIS_URL)
                r.ping()
                print(f"✅ Redis connection successful for project {project.id}")
                
                # Just start Stage 1 processing
                from celery_tasks import process_project_pipeline
                print(f"⚙️ Starting process_project_pipeline for project {project.id}, stage 1")
                task = process_project_pipeline.apply_async(
                    args=[project.id, 1, current_user.id]
                )
                print(f"📋 Stage 1 task created: {task.id}")
                flash('Project created successfully! AI agents are now processing your idea...', 'success')
                celery_available = True
            except Exception as e:
                print(f"⚠️ Celery not available: {str(e)}")
                celery_available = False
        
        # If auto_run is enabled OR Celery failed, use synchronous processing
        if auto_run or not celery_available:
            print(f"📝 Using synchronous processing for project {project.id} (auto_run={auto_run})")
            try:
                from ai_providers import AIProviderFactory
                
                if auto_run:
                    flash('Auto-run enabled! Processing all stages synchronously...', 'info')
                    
                    # Execute all stages synchronously for auto-run
                    for current_stage in range(1, 7):  # Stages 1-6
                        print(f"🔄 Auto-running Stage {current_stage}")
                        
                        # Get agents for current stage
                        stage_agents = Agent.query.filter_by(stage=current_stage, is_active=True).all()
                        if not stage_agents:
                            print(f"⚠️ No agents found for stage {current_stage}")
                            continue
                        
                        # Create tasks if they don't exist
                        for agent in stage_agents:
                            existing_task = Task.query.filter_by(
                                project_id=project.id,
                                agent_id=agent.id,
                                stage=current_stage
                            ).first()
                            
                            if not existing_task:
                                task = Task(
                                    project_id=project.id,
                                    agent_id=agent.id,
                                    title=f"{agent.name} - Stage {current_stage}",
                                    description=f"Auto-generated task for {agent.name}",
                                    stage=current_stage,
                                    status='pending'
                                )
                                db.session.add(task)
                        db.session.commit()
                        
                        # Execute all tasks for this stage
                        tasks = Task.query.filter_by(
                            project_id=project.id,
                            stage=current_stage
                        ).all()
                        
                        for task in tasks:
                            if task.assigned_agent:
                                print(f"🔥 Auto-executing {task.assigned_agent.name} for Stage {current_stage}")
                                task.status = 'processing'
                                db.session.commit()
                                
                                result = AIProviderFactory.execute_agent(
                                    agent=task.assigned_agent,
                                    prompt=project.idea_source,
                                    project_id=project.id,
                                    task_id=task.id
                                )
                                
                                if result['success']:
                                    task.status = 'completed'
                                    print(f"✅ {task.assigned_agent.name} completed")
                                else:
                                    task.status = 'failed'
                                    task.error_message = result.get('error', 'Unknown error')
                                    print(f"❌ {task.assigned_agent.name} failed")
                                
                                db.session.commit()
                        
                        # Update project stage
                        project.stage = current_stage
                        db.session.commit()
                    
                    # Update project completion percentage
                    total_tasks = Task.query.filter_by(project_id=project.id).count()
                    completed_tasks = Task.query.filter_by(project_id=project.id, status='completed').count()
                    if total_tasks > 0:
                        project.completion_percentage = round((completed_tasks / total_tasks) * 100, 2)
                        db.session.commit()
                    
                    flash('🎉 Auto-run complete! All 6 stages have been processed.', 'success')
                    
                else:
                    # Just run Stage 1 for non-auto-run
                    stage1_agents = Agent.query.filter_by(stage=1, is_active=True).all()
                    print(f"🔍 Found {len(stage1_agents)} Stage 1 agents: {[a.name for a in stage1_agents]}")
                    
                    for agent in stage1_agents:
                        task = Task.query.filter_by(project_id=project.id, agent_id=agent.id).first()
                        if task:
                            print(f"🔥 Processing task {task.id} with agent {agent.name}")
                            task.status = 'processing'
                            db.session.commit()
                            
                            result = AIProviderFactory.execute_agent(
                                agent=agent,
                                prompt=project.idea_source,
                                project_id=project.id,
                                task_id=task.id
                            )
                            
                            if result['success']:
                                task.status = 'completed'
                                flash(f'✅ {agent.name} completed successfully!', 'success')
                            else:
                                task.status = 'failed'
                                task.error_message = result.get('error', 'Unknown error')
                                flash(f'❌ {agent.name} failed: {result.get("error", "Unknown error")}', 'error')
                            
                            db.session.commit()
                    
                    # Update project completion percentage
                    total_tasks = Task.query.filter_by(project_id=project.id).count()
                    completed_tasks = Task.query.filter_by(project_id=project.id, status='completed').count()
                    if total_tasks > 0:
                        project.completion_percentage = round((completed_tasks / total_tasks) * 100, 2)
                        db.session.commit()
                    
                    flash('Project created! Stage 1 processing completed.', 'success')
                
            except Exception as sync_error:
                flash(f'Project created. Processing error: {str(sync_error)}', 'error')
        
        if request.is_json:
            return jsonify({'success': True, 'project_id': project.id})
        
        return redirect(url_for('project_detail', project_id=project.id))
    
    return render_template('new_project.html')

@app.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    project = db.get_or_404(Project, project_id)
    
    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('projects'))
    
    tasks = Task.query.filter_by(project_id=project_id).order_by(Task.created_at.desc()).all()
    executions = AgentExecution.query.filter_by(project_id=project_id).order_by(AgentExecution.created_at.desc()).limit(20).all()
    artifacts = ProjectArtifact.query.filter_by(project_id=project_id).order_by(ProjectArtifact.created_at.desc()).all()
    
    return render_template('project_detail.html',
                         project=project,
                         tasks=tasks,
                         executions=executions,
                         artifacts=artifacts)

@app.route('/agents')
@login_required
def agents():
    agents = Agent.query.order_by(Agent.stage, Agent.name).all()
    return render_template('agents.html', agents=agents)

@app.route('/agents/<int:agent_id>')
@login_required
def agent_detail(agent_id):
    agent = db.get_or_404(Agent, agent_id)
    prompts = SystemPrompt.query.filter_by(agent_id=agent_id).order_by(SystemPrompt.created_at.desc()).all()
    recent_executions = AgentExecution.query.filter_by(agent_id=agent_id).order_by(AgentExecution.created_at.desc()).limit(20).all()
    
    return render_template('agent_detail.html',
                         agent=agent,
                         prompts=prompts,
                         recent_executions=recent_executions)

@app.route('/agents/<int:agent_id>/execute', methods=['POST'])
@login_required
def execute_agent(agent_id):
    agent = db.get_or_404(Agent, agent_id)
    data = request.get_json()
    
    project_id = data.get('project_id')
    task_id = data.get('task_id')
    input_prompt = data.get('prompt')
    use_async = data.get('async', True)  # Default to async execution
    
    if use_async:
        # Use Celery for async execution
        from celery_tasks import execute_agent_async
        
        task = execute_agent_async.apply_async(
            args=[agent_id, input_prompt, project_id, task_id, current_user.id]
        )
        
        # Emit Socket.IO event for task started
        socketio.emit('agent_started', {
            'agent_id': agent_id,
            'agent_name': agent.name,
            'task_id': task.id,
            'project_id': project_id
        }, room=f'user_{current_user.id}')
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': 'Agent execution started',
            'async': True
        })
    else:
        # Synchronous execution using real AI providers
        from ai_providers import AIProviderFactory
        
        try:
            result = AIProviderFactory.execute_agent(
                agent=agent,
                prompt=input_prompt,
                project_id=project_id,
                task_id=task_id
            )
            
            # Emit Socket.IO event for completion
            socketio.emit('agent_completed', {
                'agent_id': agent_id,
                'agent_name': agent.name,
                'result': result
            }, room=f'user_{current_user.id}')
            
            return jsonify(result)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

# Auth routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# API Routes
@app.route('/api/projects/<int:project_id>/advance', methods=['POST'])
@login_required
def advance_project_stage(project_id):
    project = db.get_or_404(Project, project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    if project.stage < 6:
        next_stage = project.stage + 1
        
        try:
            # Check if Redis is available
            import redis
            r = redis.from_url(Config.REDIS_URL)
            r.ping()
            
            # Use Celery to process the pipeline for this stage
            from celery_tasks import process_project_pipeline
            
            task = process_project_pipeline.apply_async(
                args=[project_id, next_stage, current_user.id]
            )
            
            # Emit Socket.IO event
            socketio.emit('project_advancing', {
                'project_id': project_id,
                'from_stage': project.stage,
                'to_stage': next_stage,
                'task_id': task.id
            }, room=f'user_{current_user.id}')
            
            return jsonify({
                'success': True,
                'message': f'Advancing project to stage {next_stage}',
                'task_id': task.id,
                'async': True
            })
        except Exception as e:
            # Redis/Celery not available, advance stage and execute synchronously
            print(f"❌ Celery error for stage advance: {str(e)}")
            
            project.stage = next_stage
            project.updated_at = datetime.utcnow()
            
            # Update status based on stage
            stage_status_map = {
                2: 'validating',
                3: 'developing',
                4: 'marketing',
                5: 'operating',
                6: 'scaling'
            }
            project.status = stage_status_map.get(project.stage, project.status)
            db.session.commit()
            
            # Create and execute tasks for this stage synchronously
            from ai_providers import AIProviderFactory
            agents = Agent.query.filter_by(stage=next_stage, is_active=True).all()
            
            success_count = 0
            fail_count = 0
            
            for agent in agents:
                # Create the task
                task = Task(
                    project_id=project_id,
                    agent_id=agent.id,
                    title=f"{agent.name} - Stage {next_stage}",
                    description=f"Task for {agent.name}",
                    stage=next_stage,
                    status='processing'  # Start as processing
                )
                db.session.add(task)
                db.session.commit()
                
                # Execute the task immediately
                try:
                    print(f"🔥 Executing {agent.name} for Stage {next_stage}")
                    result = AIProviderFactory.execute_agent(
                        agent=agent,
                        prompt=project.idea_source or f"Process stage {next_stage} for project: {project.name}",
                        project_id=project_id,
                        task_id=task.id
                    )
                    
                    if result['success']:
                        task.status = 'completed'
                        success_count += 1
                        print(f"✅ {agent.name} completed")
                    else:
                        task.status = 'failed'
                        task.error_message = result.get('error', 'Unknown error')
                        fail_count += 1
                        print(f"❌ {agent.name} failed: {result.get('error')}")
                        
                except Exception as exec_error:
                    task.status = 'failed'
                    task.error_message = str(exec_error)[:500]  # Limit error message length
                    fail_count += 1
                    print(f"❌ {agent.name} execution error: {str(exec_error)}")
                
                db.session.commit()
                
                # Emit progress update
                socketio.emit('task_completed', {
                    'task_id': task.id,
                    'task_title': task.title,
                    'agent_name': agent.name,
                    'status': task.status
                }, room=f'user_{current_user.id}')
            
            # Update project completion percentage
            total_tasks = Task.query.filter_by(project_id=project_id).count()
            completed_tasks = Task.query.filter_by(project_id=project_id, status='completed').count()
            if total_tasks > 0:
                project.completion_percentage = round((completed_tasks / total_tasks) * 100, 2)
                db.session.commit()
            
            # Emit completion event
            socketio.emit('project_advancing', {
                'project_id': project_id,
                'from_stage': project.stage - 1,
                'to_stage': next_stage,
                'task_id': None
            }, room=f'user_{current_user.id}')
            
            return jsonify({
                'success': True,
                'message': f'Advanced to stage {next_stage}. {success_count} tasks completed, {fail_count} failed.',
                'async': False
            })
    
    return jsonify({'error': 'Project already at final stage'}), 400

@app.route('/api/projects/<int:project_id>/start-tasks', methods=['POST'])
@login_required
def start_pending_tasks(project_id):
    """Manually start pending tasks for a project"""
    project = db.get_or_404(Project, project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json() or {}
    stage = data.get('stage')
    
    # Get pending tasks - if no stage specified, get ALL pending tasks for the project
    if stage is not None:
        pending_tasks = Task.query.filter_by(
            project_id=project_id,
            stage=stage,
            status='pending'
        ).all()
    else:
        # Get all pending tasks for the project regardless of stage
        pending_tasks = Task.query.filter_by(
            project_id=project_id,
            status='pending'
        ).all()
    
    if not pending_tasks:
        # Also check for 'processing' tasks that might be stuck
        processing_tasks = Task.query.filter_by(
            project_id=project_id,
            status='processing'
        ).all()
        if processing_tasks:
            return jsonify({'error': f'{len(processing_tasks)} task(s) are already processing'}), 400
        return jsonify({'error': 'No pending tasks found'}), 400
    
    # Try to execute tasks using AI provider directly (synchronous)
    from ai_providers import AIProviderFactory
    
    executed_count = 0
    for task in pending_tasks:
        if task.assigned_agent:
            try:
                print(f"🔥 Manually starting task {task.id} with agent {task.assigned_agent.name}")
                task.status = 'processing'
                db.session.commit()
                
                # Execute directly
                result = AIProviderFactory.execute_agent(
                    agent=task.assigned_agent,
                    prompt=project.idea_source or f"Process {task.title} for project: {project.name}",
                    project_id=project_id,
                    task_id=task.id
                )
                
                if result['success']:
                    task.status = 'completed'
                    executed_count += 1
                    
                    # Emit success notification
                    socketio.emit('task_completed', {
                        'task_id': task.id,
                        'task_title': task.title,
                        'agent_name': task.assigned_agent.name
                    }, room=f'user_{current_user.id}')
                else:
                    task.status = 'failed'
                    task.error_message = result.get('error', 'Unknown error')
                    
                db.session.commit()
                
            except Exception as e:
                print(f"❌ Error executing task {task.id}: {str(e)}")
                task.status = 'failed'
                task.error_message = str(e)
                db.session.commit()
    
    if executed_count > 0:
        # Update project completion percentage
        total_tasks = Task.query.filter_by(project_id=project_id).count()
        completed_tasks = Task.query.filter_by(project_id=project_id, status='completed').count()
        if total_tasks > 0:
            project.completion_percentage = round((completed_tasks / total_tasks) * 100, 2)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Started {executed_count} task(s) successfully'
        })
    else:
        return jsonify({
            'error': 'Failed to start any tasks. Check Ollama connection.'
        }), 500

@app.route('/api/system/metrics')
@login_required
def system_metrics():
    # Calculate system-wide metrics
    total_executions = AgentExecution.query.count()
    total_cost = db.session.query(db.func.sum(AgentExecution.cost)).scalar() or 0
    avg_duration = db.session.query(db.func.avg(AgentExecution.duration_ms)).scalar() or 0
    success_rate = db.session.query(
        db.func.avg(db.case((AgentExecution.success == True, 1), else_=0))
    ).scalar() or 0
    
    return jsonify({
        'total_executions': total_executions,
        'total_cost': round(total_cost, 2),
        'avg_duration_ms': round(avg_duration),
        'success_rate': round(success_rate * 100, 2)
    })

# Socket.IO Event Handlers
@socketio.on('connect', namespace='/tasks')
def handle_connect():
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')
        emit('connected', {'message': 'Connected to real-time updates'})

@socketio.on('disconnect', namespace='/tasks')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}')

@socketio.on('subscribe_project', namespace='/tasks')
def handle_subscribe_project(data):
    project_id = data.get('project_id')
    if project_id:
        project = db.session.get(Project, project_id)
        if project and project.user_id == current_user.id:
            join_room(f'project_{project_id}')
            emit('subscribed', {'project_id': project_id})

@socketio.on('unsubscribe_project', namespace='/tasks')
def handle_unsubscribe_project(data):
    project_id = data.get('project_id')
    if project_id:
        leave_room(f'project_{project_id}')

# API endpoint for checking Celery task status
@app.route('/api/tasks/<task_id>/status')
@login_required
def check_task_status(task_id):
    try:
        # Check if Redis is available
        import redis
        r = redis.from_url(Config.REDIS_URL)
        r.ping()
        
        from celery.result import AsyncResult
        from celery_tasks import celery_app
        
        result = AsyncResult(task_id, app=celery_app)
        
        return jsonify({
            'task_id': task_id,
            'state': result.state,
            'result': result.result if result.ready() else None,
            'info': result.info
        })
    except redis.ConnectionError:
        # Redis not available, return a mock completed status
        return jsonify({
            'task_id': task_id,
            'state': 'SUCCESS',
            'result': {'message': 'Task completed (Redis not available)'},
            'info': None
        })
    except Exception as e:
        # Return error as JSON, not HTML
        return jsonify({
            'task_id': task_id,
            'state': 'FAILURE',
            'error': str(e),
            'result': None,
            'info': None
        }), 200  # Return 200 to avoid HTML error page

# API endpoint for generating artifacts
@app.route('/api/projects/<int:project_id>/artifacts/generate', methods=['POST'])
@login_required
def generate_artifact(project_id):
    project = db.get_or_404(Project, project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    artifact_type = data.get('type', 'code')
    
    try:
        # Check if Redis is available
        import redis
        r = redis.from_url(Config.REDIS_URL)
        r.ping()
        
        from celery_tasks import generate_project_artifacts
        
        task = generate_project_artifacts.apply_async(
            args=[project_id, artifact_type]
        )
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': f'Generating {artifact_type} artifact'
        })
    except:
        # Redis not available, generate synchronously
        from ai_providers import AIProviderFactory
        
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
            return jsonify({
                'success': False,
                'error': f'Agent {agent_name} not found'
            })
        
        # Generate artifact content synchronously
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
        
        # Return a fake task ID that will immediately show as complete
        import uuid
        fake_task_id = str(uuid.uuid4())
        
        return jsonify({
            'success': True,
            'task_id': fake_task_id,
            'message': f'Generating {artifact_type} artifact (synchronous mode)'
        })

@app.route('/api/projects/<int:project_id>/delete', methods=['DELETE'])
@login_required
def delete_project(project_id):
    try:
        project = db.get_or_404(Project, project_id)
        
        if project.user_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403
    except Exception as e:
        return jsonify({'error': f'Project not found: {str(e)}'}), 404
    
    try:
        # Delete all associated records (cascade should handle most of this)
        # But let's be explicit to ensure cleanup
        
        # Delete project artifacts
        ProjectArtifact.query.filter_by(project_id=project_id).delete()
        
        # Delete agent executions for this project
        AgentExecution.query.filter_by(project_id=project_id).delete()
        
        # Delete tasks for this project
        Task.query.filter_by(project_id=project_id).delete()
        
        # Delete the project itself
        db.session.delete(project)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Project deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        # Log the error for debugging
        print(f"Delete project error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/debug/project/<int:project_id>', methods=['GET'])
@login_required
def debug_project(project_id):
    """Debug route to check project access"""
    try:
        project = db.get_or_404(Project, project_id)
        return jsonify({
            'success': True,
            'project_id': project.id,
            'project_name': project.name,
            'user_id': project.user_id,
            'current_user_id': current_user.id,
            'can_delete': project.user_id == current_user.id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/test-ollama', methods=['GET'])
@login_required  
def test_ollama():
    """Test Ollama connection and model"""
    try:
        from ai_providers import AIProviderFactory
        
        provider = AIProviderFactory.get_provider()
        
        # Test with a simple prompt
        response = provider.generate("Hello, please respond with 'Ollama is working!'")
        
        return jsonify({
            'success': response.success,
            'content': response.content,
            'tokens_used': response.tokens_used,
            'cost': response.cost,
            'error': response.error_message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<int:project_id>/export')
@login_required
def export_project(project_id):
    """Export all project data and artifacts as a ZIP file"""
    import zipfile
    import io
    from datetime import datetime
    
    project = db.get_or_404(Project, project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Create a ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Get all project data
        tasks = Task.query.filter_by(project_id=project_id).order_by(Task.stage).all()
        executions = AgentExecution.query.filter_by(project_id=project_id).all()
        artifacts = ProjectArtifact.query.filter_by(project_id=project_id).all()
        
        # Create project summary
        summary = f"""# {project.name}

## Project Overview
- **Status**: {project.status}
- **Stage**: {project.stage}/6
- **Completion**: {project.completion_percentage}%
- **Created**: {project.created_at.strftime('%Y-%m-%d %H:%M')}

## Description
{project.description or 'No description provided'}

## Original Idea
{project.idea_source}

## Tasks Summary
Total Tasks: {len(tasks)}
- Completed: {sum(1 for t in tasks if t.status == 'completed')}
- Failed: {sum(1 for t in tasks if t.status == 'failed')}
- Pending: {sum(1 for t in tasks if t.status == 'pending')}
"""
        zip_file.writestr('README.md', summary)
        
        # Export tasks by stage
        for stage in range(1, 7):
            stage_tasks = [t for t in tasks if t.stage == stage]
            if stage_tasks:
                stage_content = f"# Stage {stage} Tasks\n\n"
                for task in stage_tasks:
                    stage_content += f"## {task.title}\n"
                    stage_content += f"**Status**: {task.status}\n"
                    stage_content += f"**Agent**: {task.assigned_agent.name if task.assigned_agent else 'Unassigned'}\n"
                    stage_content += f"**Description**: {task.description}\n\n"
                    
                    # Add execution output if available
                    task_executions = [e for e in executions if e.task_id == task.id]
                    for exec in task_executions:
                        if exec.success and exec.output_response:
                            stage_content += f"### Output\n```\n{exec.output_response}\n```\n\n"
                
                zip_file.writestr(f'stages/stage_{stage}.md', stage_content)
        
        # Export artifacts
        for artifact in artifacts:
            filename = f"artifacts/{artifact.type}/{artifact.name.replace('/', '_')}.md"
            content = f"# {artifact.name}\n\n{artifact.content or 'No content'}"
            zip_file.writestr(filename, content)
        
        # Export agent outputs
        for execution in executions:
            if execution.success and execution.output_response:
                agent_name = execution.agent.name.replace(' ', '_')
                filename = f"agent_outputs/{agent_name}_{execution.id}.md"
                content = f"""# {execution.agent.name} Output

**Executed**: {execution.created_at.strftime('%Y-%m-%d %H:%M')}
**Duration**: {execution.duration_ms}ms
**Cost**: ${execution.cost or 0:.4f}

## Output
{execution.output_response}
"""
                zip_file.writestr(filename, content)
        
        # Create HTML viewer
        html_content = create_export_html(project, tasks, executions, artifacts)
        zip_file.writestr('index.html', html_content)
    
    # Prepare the ZIP file for download
    zip_buffer.seek(0)
    
    from flask import send_file
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{project.name.replace(" ", "_")}_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    )

def create_export_html(project, tasks, executions, artifacts):
    """Create a beautiful HTML viewer for exported project data"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project.name} - Project Export</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2.5em;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 20px;
        }}
        .stat {{
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 5px;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .task {{
            background: #f8f9fa;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 4px solid #667eea;
        }}
        .status {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 3px;
            font-size: 0.9em;
            font-weight: bold;
        }}
        .status.completed {{ background: #28a745; color: white; }}
        .status.failed {{ background: #dc3545; color: white; }}
        .status.pending {{ background: #ffc107; color: black; }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 5px;
            border-radius: 3px;
        }}
        .progress-bar {{
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            transition: width 0.3s ease;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{project.name}</h1>
            <p>{project.description or 'AI-Powered Business Automation Project'}</p>
            <div class="stats">
                <div class="stat">Stage {project.stage}/6</div>
                <div class="stat">{len([t for t in tasks if t.status == 'completed'])} Tasks Completed</div>
                <div class="stat">{len(artifacts)} Artifacts</div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {project.completion_percentage}%">
                    {project.completion_percentage}% Complete
                </div>
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>📋 Project Overview</h2>
                <p><strong>Original Idea:</strong></p>
                <blockquote style="background: #f8f9fa; padding: 20px; border-left: 4px solid #667eea; font-style: italic;">
                    {project.idea_source or 'No idea source provided'}
                </blockquote>
            </div>
            
            <div class="section">
                <h2>🎯 Tasks by Stage</h2>
                {''.join([f"""
                <h3>Stage {stage} - {['', 'Input Layer', 'Validation & Strategy', 'Development', 'Go-to-Market', 'Operations', 'Self-Improvement'][stage]}</h3>
                {''.join([f'''
                <div class="task">
                    <h4>{task.title}</h4>
                    <span class="status {task.status}">{task.status.upper()}</span>
                    <p><em>{task.description}</em></p>
                    {f'<p><strong>Agent:</strong> {task.assigned_agent.name}</p>' if task.assigned_agent else ''}
                </div>
                ''' for task in tasks if task.stage == stage]) or '<p>No tasks for this stage</p>'}
                """ for stage in range(1, 7)])}
            </div>
            
            <div class="section">
                <h2>🎨 Generated Artifacts</h2>
                {(''.join([f"""
                <div class="task">
                    <h4>{artifact.name}</h4>
                    <p><strong>Type:</strong> {artifact.type}</p>
                    <pre>{artifact.content if artifact.content else 'No content'}</pre>
                </div>
                """ for artifact in artifacts]) if artifacts else '<p>No artifacts generated yet</p>')}
            </div>
            
            <div class="section">
                <h2>🤖 Agent Outputs</h2>
                {(''.join([f"""
                <div class="task">
                    <h4>{exec.agent.name}</h4>
                    <p><strong>Executed:</strong> {exec.created_at.strftime('%Y-%m-%d %H:%M')}</p>
                    <p><strong>Duration:</strong> {exec.duration_ms}ms | <strong>Cost:</strong> ${exec.cost or 0:.4f}</p>
                    <pre>{exec.output_response if exec.output_response else 'No output'}</pre>
                </div>
                """ for exec in executions if exec.success and exec.output_response]) if executions else '<p>No agent outputs yet</p>')}
            </div>
        </div>
    </div>
</body>
</html>"""

if __name__ == '__main__':
    init_database()
    # Use Socket.IO run instead of app.run for WebSocket support
    # Note: allow_unsafe_werkzeug is needed for development mode
    socketio.run(app, debug=True, port=5001, allow_unsafe_werkzeug=True)