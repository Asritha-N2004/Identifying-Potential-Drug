"""Download workspace-only official database runtimes and Docker Compose."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import zipfile
import httpx

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'runtime/integration-tools'


def download(name,url,checksum=None,extract=True):
    target=TOOLS/name
    if not target.exists():
        print(f'Downloading {name}',flush=True)
        with httpx.stream('GET',url,follow_redirects=True,timeout=120) as response:
            response.raise_for_status()
            with target.with_suffix('.partial').open('wb') as output:
                for data in response.iter_bytes():output.write(data)
        target.with_suffix('.partial').replace(target)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    if checksum and digest.lower()!=checksum.lower():raise ValueError(f'Checksum mismatch: {name}')
    if extract:
        output=TOOLS/name.removesuffix('.zip')
        if not output.exists():
            with zipfile.ZipFile(target) as archive:
                for member in archive.infolist():
                    path=(output/member.filename).resolve()
                    if not path.is_relative_to(output.resolve()):raise ValueError('Unsafe archive path')
                archive.extractall(output)
    print(f'Ready: {name}',flush=True)
    return {'file':name,'url':url,'sha256':digest,'upstream_checksum_verified':bool(checksum)}


if __name__=='__main__':
    TOOLS.mkdir(parents=True,exist_ok=True)
    with httpx.Client(timeout=30,follow_redirects=True) as client:
        java=client.get('https://api.adoptium.net/v3/assets/latest/21/hotspot',params={'architecture':'x64','image_type':'jre','os':'windows','vendor':'eclipse'})
        java.raise_for_status();package=java.json()[0]['binary']['package']
        compose=client.get('https://api.github.com/repos/docker/compose/releases/tags/v5.7.0')
        compose.raise_for_status()
        assets={a['name']:a for a in compose.json()['assets']}
        compose_asset=assets['docker-compose-windows-x86_64.exe']
        checksum=client.get(assets['checksums.txt']['browser_download_url']);checksum.raise_for_status()
        compose_hash=next(line.split()[0] for line in checksum.text.splitlines() if line.split()[-1].lstrip('*')=='docker-compose-windows-x86_64.exe')
    jobs=[('postgresql-16.15-windows.zip','https://get.enterprisedb.com/postgresql/postgresql-16.15-1-windows-x64-binaries.zip',None,True),
          ('neo4j-5.26.33-windows.zip','https://dist.neo4j.org/neo4j-community-5.26.33-windows.zip',None,True),
          ('java21.zip',package['link'],package['checksum'],True),
          ('docker-compose.exe',compose_asset['browser_download_url'],compose_hash,False)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda args:download(*args),jobs))
    (TOOLS/'downloads.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print('Saved runtime/integration-tools/downloads.json',flush=True)
