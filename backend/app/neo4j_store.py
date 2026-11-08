"""Parameterized Neo4j persistence with stable edge provenance keys."""
import hashlib,json

class Neo4jStore:
    def __init__(self,uri,user,password):
        from neo4j import GraphDatabase
        self.driver=GraphDatabase.driver(uri,auth=(user,password))

    def sync(self,kg):
        self.driver.verify_connectivity()
        nodes=[{'id':e.id,'kind':e.kind,'name':e.name,'json':json.dumps(e.model_dump())} for e in kg.entities.values()]
        edges=[]
        for e in kg.dataset.relationships:
            data=e.model_dump(mode='json')
            edges.append({'id':hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),'source':e.source,'target':e.target,'relation':e.relation,'json':json.dumps(data)})
        with self.driver.session() as s:
            s.run('CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE').consume()
            s.run('UNWIND $nodes AS n MERGE (e:Entity {id:n.id}) SET e.kind=n.kind,e.name=n.name,e.json=n.json',nodes=nodes).consume()
            s.run('UNWIND $edges AS e MATCH (a:Entity {id:e.source}),(b:Entity {id:e.target}) MERGE (a)-[r:BIOMEDICAL {id:e.id}]->(b) SET r.relation=e.relation,r.json=e.json',edges=edges).consume()

    def close(self):
        self.driver.close()
