"""Validate a curated Dataset JSON, optionally synchronizing Neo4j."""
import argparse,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.graph import KnowledgeGraph

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('dataset',type=Path);parser.add_argument('--neo4j',action='store_true');args=parser.parse_args()
    graph=KnowledgeGraph.load(args.dataset)
    print(graph.statistics())
    if args.neo4j:
        from backend.app.neo4j_store import Neo4jStore
        store=Neo4jStore(os.environ['NEO4J_URI'],os.getenv('NEO4J_USERNAME','neo4j'),os.environ['NEO4J_PASSWORD'])
        try:store.sync(graph)
        finally:store.close()
