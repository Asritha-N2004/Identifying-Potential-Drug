"""Retrieve raw timestamped source records; no automatic evidence assertions."""
import argparse,asyncio,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.connectors import CLIENTS

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',choices=CLIENTS)
    parser.add_argument('query')
    parser.add_argument('--page',type=int,default=0)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.page<0:parser.error('page must be nonnegative')
    envelope=asyncio.run(CLIENTS[args.source]().search(args.query,args.page))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(envelope.model_dump_json(indent=2),encoding='utf-8')
    print(f'Saved unreviewed source envelope: {args.output}')
