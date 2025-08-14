from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json
from enum import Enum

db = SQLAlchemy()

class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"

class ProjectStatus(Enum):
    IDEA = "idea"
    VALIDATING = "validating"
    DEVELOPING = "developing"
    MARKETING = "marketing"
    OPERATING = "operating"
    SCALING = "scaling"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    projects = db.relationship('Project', backref='owner', lazy='dynamic')
    api_keys = db.relationship('APIKey', backref='user', lazy='dynamic')

class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    idea_source = db.Column(db.Text)  # Original idea/prompt
    status = db.Column(db.String(50), default=ProjectStatus.IDEA.value)
    stage = db.Column(db.Integer, default=1)  # 1-6 stages
    
    # Metrics
    estimated_revenue = db.Column(db.Float, default=0)
    development_cost = db.Column(db.Float, default=0)
    operation_cost = db.Column(db.Float, default=0)
    completion_percentage = db.Column(db.Float, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    tasks = db.relationship('Task', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    executions = db.relationship('AgentExecution', backref='project', lazy='dynamic')
    artifacts = db.relationship('ProjectArtifact', backref='project', lazy='dynamic', cascade='all, delete-orphan')

class Agent(db.Model):
    __tablename__ = 'agents'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    type = db.Column(db.String(50))  # validation, development, marketing, operations, etc.
    stage = db.Column(db.Integer)  # Which stage (1-6) this agent belongs to
    icon = db.Column(db.String(10))  # Emoji icon
    color = db.Column(db.String(20))  # Color theme
    
    description = db.Column(db.Text)
    capabilities = db.Column(db.JSON)  # List of capabilities
    
    # AI Configuration
    ai_provider = db.Column(db.String(50))  # openai, anthropic, google
    model_name = db.Column(db.String(100))  # gpt-4, claude-3, gemini-pro
    temperature = db.Column(db.Float, default=0.7)
    max_tokens = db.Column(db.Integer, default=2000)
    
    # Status
    status = db.Column(db.String(20), default=AgentStatus.IDLE.value)
    last_active = db.Column(db.DateTime)
    total_executions = db.Column(db.Integer, default=0)
    success_rate = db.Column(db.Float, default=0)
    
    # Configuration
    is_active = db.Column(db.Boolean, default=True)
    auto_execute = db.Column(db.Boolean, default=False)
    retry_attempts = db.Column(db.Integer, default=3)
    timeout_seconds = db.Column(db.Integer, default=300)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    prompts = db.relationship('SystemPrompt', backref='agent', lazy='dynamic', cascade='all, delete-orphan')
    executions = db.relationship('AgentExecution', backref='agent', lazy='dynamic')
    tasks = db.relationship('Task', backref='assigned_agent', lazy='dynamic')

class SystemPrompt(db.Model):
    __tablename__ = 'system_prompts'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    name = db.Column(db.String(100))
    version = db.Column(db.String(20), default='1.0')
    
    role = db.Column(db.Text)
    instructions = db.Column(db.Text)
    examples = db.Column(db.JSON)  # List of example interactions
    constraints = db.Column(db.JSON)  # List of constraints/rules
    tools = db.Column(db.JSON)  # Available tools/functions
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))
    parent_task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    input_data = db.Column(db.JSON)
    output_data = db.Column(db.JSON)
    
    status = db.Column(db.String(20), default=TaskStatus.PENDING.value)
    priority = db.Column(db.Integer, default=5)  # 1-10, higher is more important
    stage = db.Column(db.Integer)  # Which stage this task belongs to
    
    estimated_duration = db.Column(db.Integer)  # In seconds
    actual_duration = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    
    # Self-referential relationship for subtasks
    subtasks = db.relationship('Task', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

class AgentExecution(db.Model):
    __tablename__ = 'agent_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    
    input_prompt = db.Column(db.Text)
    output_response = db.Column(db.Text)
    
    tokens_used = db.Column(db.Integer)
    cost = db.Column(db.Float)
    duration_ms = db.Column(db.Integer)
    
    success = db.Column(db.Boolean)
    error_message = db.Column(db.Text)
    
    execution_metadata = db.Column(db.JSON)  # Additional execution details
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProjectArtifact(db.Model):
    __tablename__ = 'project_artifacts'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    
    type = db.Column(db.String(50))  # code, design, document, deployment, etc.
    name = db.Column(db.String(200))
    description = db.Column(db.Text)
    
    file_path = db.Column(db.String(500))
    url = db.Column(db.String(500))
    content = db.Column(db.Text)  # For storing text/code directly
    artifact_metadata = db.Column(db.JSON)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))

class APIKey(db.Model):
    __tablename__ = 'api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    provider = db.Column(db.String(50))  # openai, anthropic, google, github, etc.
    key_name = db.Column(db.String(100))
    encrypted_key = db.Column(db.String(500))  # Store encrypted
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)

class SystemMetrics(db.Model):
    __tablename__ = 'system_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    
    metric_type = db.Column(db.String(50))  # cost, performance, success_rate
    metric_name = db.Column(db.String(100))
    value = db.Column(db.Float)
    unit = db.Column(db.String(20))
    
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    metrics_metadata = db.Column(db.JSON)