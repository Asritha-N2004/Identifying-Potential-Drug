"""SQL job persistence; SQLite offline and PostgreSQL deployment share models."""
import os
from datetime import datetime,timezone
from sqlalchemy import create_engine, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

class Base(DeclarativeBase):
    pass

class Job(Base):
    __tablename__='jobs'
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    kind: Mapped[str]=mapped_column(String(30))
    status: Mapped[str]=mapped_column(String(20),index=True)
    payload: Mapped[dict]=mapped_column(JSON,default=dict)
    result: Mapped[dict]=mapped_column(JSON,default=dict)
    error: Mapped[str|None]=mapped_column(String,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class AgentExecution(Base):
    __tablename__='agent_executions'
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    job_id: Mapped[str]=mapped_column(ForeignKey('jobs.id'),index=True)
    agent_name: Mapped[str]=mapped_column(String(100))
    status: Mapped[str]=mapped_column(String(20))
    duration_seconds: Mapped[float]
    output: Mapped[dict]=mapped_column(JSON)

class EntityRecord(Base):
    __tablename__='entities'
    id: Mapped[str]=mapped_column(String(150),primary_key=True)
    kind: Mapped[str]=mapped_column(String(30),index=True)
    name: Mapped[str]=mapped_column(String(300),index=True)
    data: Mapped[dict]=mapped_column(JSON)

class RelationshipRecord(Base):
    __tablename__='relationships'
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    source_id: Mapped[str]=mapped_column(ForeignKey('entities.id'),index=True)
    target_id: Mapped[str]=mapped_column(ForeignKey('entities.id'),index=True)
    data: Mapped[dict]=mapped_column(JSON)

class Store:
    def __init__(self,url=None):
        url=url or os.getenv('DATABASE_URL','sqlite:///runtime/platform.db')
        self.engine=create_engine(url,connect_args={'check_same_thread':False} if url.startswith('sqlite') else {},pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self.session=sessionmaker(self.engine,expire_on_commit=False)

    def seed(self,kg):
        import hashlib,json
        with self.session.begin() as s:
            for e in kg.entities.values():
                s.merge(EntityRecord(id=e.id,kind=e.kind,name=e.name,data=e.model_dump()))
            s.flush()
            for e in kg.dataset.relationships:
                data=e.model_dump(mode='json')
                key=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
                s.merge(RelationshipRecord(id=key,source_id=e.source,target_id=e.target,data=data))

    def create_job(self,id,kind,payload):
        with self.session.begin() as s:
            s.add(Job(id=id,kind=kind,status='queued',payload=payload,result={}))

    def update(self,id,**values):
        with self.session.begin() as s:
            job=s.get(Job,id)
            for key,value in values.items():setattr(job,key,value)

    def get(self,id):
        with self.session() as s:
            job=s.get(Job,id)
            if job is None:return None
            return {k:getattr(job,k) for k in ['id','kind','status','payload','result','error','created_at']}

    def log(self,job_id,name,duration,output,status='complete'):
        from uuid import uuid4
        with self.session.begin() as s:
            s.add(AgentExecution(id=str(uuid4()),job_id=job_id,agent_name=name,status=status,duration_seconds=duration,output=output))

    def logs(self,job_id):
        from sqlalchemy import select
        with self.session() as s:
            return [{'agent_name':e.agent_name,'status':e.status,'duration_seconds':e.duration_seconds,'output_summary':e.output} for e in s.scalars(select(AgentExecution).where(AgentExecution.job_id==job_id))]
